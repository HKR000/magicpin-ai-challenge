"""Vera Context Engine - Storage, Versioning, Ingestion, and Retrieval."""

from __future__ import annotations
import threading
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar, TYPE_CHECKING
from pydantic import Field, ValidationError

from vera.context.diff import FieldChange, compute_payload_diff
from vera.context.provenance import FactProvenance, ProvenanceTracker
from vera.models.base import VeraBaseModel
from vera.models.category import CategoryContext
from vera.models.context_version import ContextAck, ContextEnvelope, ContextScope
from vera.models.conversation import ConversationStage, ConversationState, ConversationTurn, Role, State
from vera.conversation.machine import ConversationStateMachine
from vera.conversation.persistence import ConversationStore
from vera.conversation.transitions import TransitionInput, TransitionResult
from vera.models.customer import CustomerContext
from vera.models.merchant import MerchantContext
from vera.models.trigger import TriggerContext
from vera.models.intent import IntentType
from vera.models.validation import ValidationErrorDetail, ValidationResult, ValidationStatus

if TYPE_CHECKING:
    from vera.models.selection import SelectionBundle
    from vera.models.decision import Decision

T = TypeVar("T", bound=VeraBaseModel)




class StoredEntity(VeraBaseModel, Generic[T]):
    """Versioned entity container."""

    context_id: str = Field(..., min_length=1)
    scope: ContextScope = Field(...)
    version: int = Field(..., ge=1)
    delivered_at: str = Field(...)
    stored_at: str = Field(...)
    model: T = Field(...)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    version_history: List[int] = Field(default_factory=list)
    recent_changes: List[FieldChange] = Field(default_factory=list)


class IngestionOutcome(VeraBaseModel):
    """Result of attempting to ingest a context envelope."""

    accepted: bool = Field(..., description="Whether context was accepted")
    ack_id: Optional[str] = Field(default=None, description="Ack ID if accepted")
    stored_at: Optional[str] = Field(default=None, description="Storage timestamp")
    reason: Optional[str] = Field(default=None, description="Rejection or informational note")
    current_version: Optional[int] = Field(default=None, description="Stored version on 409 conflict")
    changed_fields: List[FieldChange] = Field(default_factory=list, description="Fields modified if update")
    validation: Optional[ValidationResult] = Field(default=None, description="Schema validation audit")

    def to_http_ack(self) -> ContextAck:
        """Render to standard challenge HTTP ContextAck schema."""
        return ContextAck(
            accepted=self.accepted,
            ack_id=self.ack_id,
            stored_at=self.stored_at,
            reason=self.reason,
            current_version=self.current_version,
        )


class AssembledContext(VeraBaseModel):
    """Assembled 4-context bundle ready for decision engine."""

    category: CategoryContext = Field(..., description="Category context for merchant vertical")
    merchant: MerchantContext = Field(..., description="Target merchant operational state")
    trigger: TriggerContext = Field(..., description="Initiating trigger event")
    customer: Optional[CustomerContext] = Field(default=None, description="Customer profile if customer-facing")
    conversation: Optional[ConversationState] = Field(default=None, description="Current conversation thread if active")
    merchant_changes: List[FieldChange] = Field(default_factory=list, description="Recent changes on merchant context")
    category_changes: List[FieldChange] = Field(default_factory=list, description="Recent changes on category context")


class ContextEngine:
    """Core stateful context manager for Vera."""

    def __init__(self):
        self._lock = threading.RLock()
        self.provenance = ProvenanceTracker()

        # Partitioned context stores: context_id -> StoredEntity[Model]
        self._categories: Dict[str, StoredEntity[CategoryContext]] = {}
        self._merchants: Dict[str, StoredEntity[MerchantContext]] = {}
        self._customers: Dict[str, StoredEntity[CustomerContext]] = {}
        self._triggers: Dict[str, StoredEntity[TriggerContext]] = {}

        # Conversation state store & state machine
        self.conversation_store = ConversationStore()
        self.state_machine = ConversationStateMachine()
        self._conversations: Dict[str, ConversationState] = self.conversation_store._conversations

    # =========================================================================
    # INGESTION & VERSIONING
    # =========================================================================

    def ingest(
        self,
        scope: ContextScope | str,
        context_id: str,
        version: int,
        payload: Dict[str, Any],
        delivered_at: Optional[str] = None,
        source: str = "context_push",
    ) -> IngestionOutcome:
        """Ingests, validates, and stores a context envelope with strict versioning."""
        with self._lock:
            # Normalize scope enum
            if isinstance(scope, str):
                try:
                    scope = ContextScope(scope)
                except ValueError:
                    return IngestionOutcome(
                        accepted=False,
                        reason="invalid_scope",
                        validation=ValidationResult(
                            status=ValidationStatus.INVALID,
                            entity_type="ContextEnvelope",
                            errors=[
                                ValidationErrorDetail(
                                    field="scope",
                                    message=f"Invalid scope '{scope}'. Allowed: {[s.value for s in ContextScope]}",
                                    invalid_value=scope,
                                )
                            ],
                        ),
                    )

            now_iso = datetime.utcnow().isoformat() + "Z"
            deliv_iso = delivered_at or now_iso

            # Step 1: Validate payload into strongly-typed entity model
            model_instance, val_res = self._validate_payload(scope, payload)
            if not val_res.is_valid or model_instance is None:
                return IngestionOutcome(
                    accepted=False,
                    reason="validation_error",
                    validation=val_res,
                )

            # Step 2: Determine appropriate storage partition
            partition = self._get_partition(scope)
            existing = partition.get(context_id)

            # Step 3: Handle Version Conflicts (Idempotency and Stale Updates)
            if existing is not None:
                if version < existing.version:
                    # 409 Conflict: Incoming version is stale
                    return IngestionOutcome(
                        accepted=False,
                        reason="stale_version",
                        current_version=existing.version,
                        validation=ValidationResult.success(entity_type=scope.value),
                    )
                elif version == existing.version:
                    # Idempotent no-op
                    return IngestionOutcome(
                        accepted=True,
                        ack_id=f"ack_{context_id}_v{version}",
                        stored_at=existing.stored_at,
                        reason="idempotent_no_op",
                        current_version=existing.version,
                        validation=ValidationResult.success(entity_type=scope.value),
                    )

            # Step 4: Higher version or initial insertion -> Compute diff
            changed_fields: List[FieldChange] = []
            version_history: List[int] = []

            if existing is not None:
                changed_fields = compute_payload_diff(existing.raw_payload, payload)
                version_history = list(existing.version_history) + [existing.version]

            # Step 5: Store atomically
            stored = StoredEntity(
                context_id=context_id,
                scope=scope,
                version=version,
                delivered_at=deliv_iso,
                stored_at=now_iso,
                model=model_instance,
                raw_payload=payload,
                version_history=version_history,
                recent_changes=changed_fields,
            )
            partition[context_id] = stored

            # Step 6: Record Provenance
            self.provenance.index_payload(
                scope=scope.value,
                entity_id=context_id,
                version=version,
                payload=payload,
                source=source,
                recorded_at=now_iso,
            )

            return IngestionOutcome(
                accepted=True,
                ack_id=f"ack_{context_id}_v{version}",
                stored_at=now_iso,
                current_version=version,
                changed_fields=changed_fields,
                validation=ValidationResult.success(entity_type=scope.value),
            )

    def _validate_payload(
        self, scope: ContextScope, payload: Dict[str, Any]
    ) -> Tuple[Optional[VeraBaseModel], ValidationResult]:
        """Validates payload against scope schema."""
        model_cls_map = {
            ContextScope.CATEGORY: CategoryContext,
            ContextScope.MERCHANT: MerchantContext,
            ContextScope.CUSTOMER: CustomerContext,
            ContextScope.TRIGGER: TriggerContext,
        }
        cls = model_cls_map[scope]
        try:
            instance = cls.model_validate(payload)
            return instance, ValidationResult.success(entity_type=cls.__name__)
        except ValidationError as exc:
            return None, ValidationResult.from_pydantic_error(entity_type=cls.__name__, exc=exc)

    def _get_partition(self, scope: ContextScope) -> Dict[str, StoredEntity]:
        if scope == ContextScope.CATEGORY:
            return self._categories
        elif scope == ContextScope.MERCHANT:
            return self._merchants
        elif scope == ContextScope.CUSTOMER:
            return self._customers
        elif scope == ContextScope.TRIGGER:
            return self._triggers
        raise ValueError(f"Unknown scope: {scope}")

    # =========================================================================
    # RETRIEVAL
    # =========================================================================

    def get_category(self, slug: str) -> Optional[CategoryContext]:
        with self._lock:
            stored = self._categories.get(slug)
            return stored.model if stored else None

    def get_merchant(self, merchant_id: str) -> Optional[MerchantContext]:
        with self._lock:
            stored = self._merchants.get(merchant_id)
            return stored.model if stored else None

    def get_customer(self, customer_id: str) -> Optional[CustomerContext]:
        with self._lock:
            stored = self._customers.get(customer_id)
            return stored.model if stored else None

    def get_trigger(self, trigger_id: str) -> Optional[TriggerContext]:
        with self._lock:
            stored = self._triggers.get(trigger_id)
            return stored.model if stored else None

    def get_stored_entity(self, scope: ContextScope, context_id: str) -> Optional[StoredEntity]:
        with self._lock:
            return self._get_partition(scope).get(context_id)

    def get_recent_changes(self, scope: ContextScope, context_id: str) -> List[FieldChange]:
        with self._lock:
            stored = self.get_stored_entity(scope, context_id)
            return stored.recent_changes if stored else []

    def get_counts(self) -> Dict[str, int]:
        """Returns loaded context counts matching /v1/healthz specification."""
        with self._lock:
            return {
                "category": len(self._categories),
                "merchant": len(self._merchants),
                "customer": len(self._customers),
                "trigger": len(self._triggers),
            }

    # =========================================================================
    # ASSEMBLE CONTEXT (for Decision & Generation Layers)
    # =========================================================================

    def assemble_context(
        self,
        merchant_id: str,
        trigger_id: str,
        customer_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Tuple[Optional[AssembledContext], Optional[str]]:
        """Assembles the full 4-context bundle. Returns (bundle, error_reason)."""
        with self._lock:
            # 1. Fetch Trigger
            trigger = self.get_trigger(trigger_id)
            if not trigger:
                return None, f"Trigger '{trigger_id}' not found"

            # 2. Fetch Merchant
            target_mid = merchant_id or trigger.merchant_id
            merchant = self.get_merchant(target_mid)
            if not merchant:
                return None, f"Merchant '{target_mid}' not found"

            # 3. Fetch Category
            category = self.get_category(merchant.category_slug)
            if not category:
                return None, f"Category '{merchant.category_slug}' for merchant '{target_mid}' not found"

            # 4. Fetch Customer if specified or if trigger is customer-scoped
            target_cid = customer_id or trigger.customer_id
            customer = None
            if target_cid:
                customer = self.get_customer(target_cid)
                if not customer:
                    return None, f"Customer '{target_cid}' not found"

            # 5. Fetch Conversation if requested
            conv = self.get_conversation(conversation_id) if conversation_id else None

            # 6. Retrieve recent changes if any
            m_changes = self.get_recent_changes(ContextScope.MERCHANT, target_mid)
            c_changes = self.get_recent_changes(ContextScope.CATEGORY, merchant.category_slug)

            bundle = AssembledContext(
                category=category,
                merchant=merchant,
                trigger=trigger,
                customer=customer,
                conversation=conv,
                merchant_changes=m_changes,
                category_changes=c_changes,
            )
            return bundle, None

    def select_context(
        self,
        merchant_id: str,
        trigger_id: str,
        customer_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        intent: Optional[Any] = None,
    ) -> Tuple[Optional[SelectionBundle], Optional[str]]:
        """Assembles context and filters/prioritizes facts via ContextSelector."""
        from vera.context.selector import ContextSelector

        assembled, err = self.assemble_context(
            merchant_id=merchant_id,
            trigger_id=trigger_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
        )
        if err or not assembled:
            return None, err

        with self._lock:
            # Capture actual versions stored in engine
            t_ent = self.get_stored_entity(ContextScope.TRIGGER, trigger_id)
            m_ent = self.get_stored_entity(ContextScope.MERCHANT, merchant_id)
            c_ent = self.get_stored_entity(ContextScope.CATEGORY, assembled.category.slug)
            cu_ent = (
                self.get_stored_entity(ContextScope.CUSTOMER, assembled.customer.customer_id)
                if assembled.customer
                else None
            )

            versions = {
                "trigger": t_ent.version if t_ent else 1,
                "merchant": m_ent.version if m_ent else 1,
                "category": c_ent.version if c_ent else 1,
            }
            if cu_ent:
                versions["customer"] = cu_ent.version

        selector = ContextSelector()
        bundle = selector.select(
            category=assembled.category,
            merchant=assembled.merchant,
            trigger=assembled.trigger,
            customer=assembled.customer,
            conversation=assembled.conversation,
            intent=intent,
            context_versions=versions,
        )
        return bundle, None

    def decide(
        self,
        merchant_id: str,
        trigger_id: str,
        customer_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        intent: Optional[Any] = None,
    ) -> Tuple[Optional[Decision], Optional[str]]:
        """Assembles context and produces a structured Level 8 Decision."""
        from vera.decision.engine import DecisionEngine

        assembled, err = self.assemble_context(
            merchant_id=merchant_id,
            trigger_id=trigger_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
        )
        if err or not assembled:
            return None, err

        with self._lock:
            t_ent = self.get_stored_entity(ContextScope.TRIGGER, trigger_id)
            m_ent = self.get_stored_entity(ContextScope.MERCHANT, merchant_id)
            c_ent = self.get_stored_entity(ContextScope.CATEGORY, assembled.category.slug)
            cu_ent = (
                self.get_stored_entity(ContextScope.CUSTOMER, assembled.customer.customer_id)
                if assembled.customer
                else None
            )

            versions = {
                "trigger": t_ent.version if t_ent else 1,
                "merchant": m_ent.version if m_ent else 1,
                "category": c_ent.version if c_ent else 1,
            }
            if cu_ent:
                versions["customer"] = cu_ent.version

        decision_engine = DecisionEngine()
        decision = decision_engine.decide(
            category=assembled.category,
            merchant=assembled.merchant,
            trigger=assembled.trigger,
            customer=assembled.customer,
            conversation=assembled.conversation,
            intent=intent,
            context_versions=versions,
        )
        return decision, None



    # =========================================================================
    # CONVERSATION CONTEXT STATE
    # =========================================================================

    def create_or_get_conversation(
        self,
        conversation_id: str,
        merchant_id: str,
        customer_id: Optional[str] = None,
        trigger_id: Optional[str] = None,
    ) -> ConversationState:
        with self._lock:
            if conversation_id in self._conversations:
                return self._conversations[conversation_id]

            now_iso = datetime.utcnow().isoformat() + "Z"
            conv = ConversationState(
                conversation_id=conversation_id,
                merchant_id=merchant_id,
                customer_id=customer_id,
                trigger_id=trigger_id,
                stage=ConversationStage.INITIATED,
                current_state=State.INITIAL,
                turns=[],
                auto_reply_count=0,
                consecutive_repeated_messages=0,
                last_message_at=now_iso,
                is_active=True,
            )
            self._conversations[conversation_id] = conv
            return conv

    def get_conversation(self, conversation_id: str) -> Optional[ConversationState]:
        with self._lock:
            return self._conversations.get(conversation_id)

    def add_turn(
        self,
        conversation_id: str,
        from_role: Role | str,
        message: str,
        timestamp: Optional[str] = None,
        detected_intent: Optional[str] = None,
        action_taken: Optional[str] = None,
    ) -> Optional[ConversationTurn]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return None

            if isinstance(from_role, str):
                from_role = Role(from_role)

            turn_num = len(conv.turns) + 1
            ts = timestamp or (datetime.utcnow().isoformat() + "Z")

            turn = ConversationTurn(
                turn_number=turn_num,
                from_role=from_role,
                message=message,
                timestamp=ts,
                detected_intent=detected_intent,
                action_taken=action_taken,
            )
            conv.turns.append(turn)
            conv.last_message_at = ts
            return turn

    def update_conversation_stage(
        self, conversation_id: str, stage: ConversationStage
    ) -> bool:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return False
            conv.stage = stage
            # Synchronize Level 6 State
            if stage == ConversationStage.INITIATED:
                conv.current_state = State.INITIAL
            elif stage == ConversationStage.QUALIFYING:
                conv.current_state = State.INTERESTED
            elif stage == ConversationStage.WAITING:
                conv.current_state = State.WAITING
            elif stage == ConversationStage.ACTION_COMMITTED:
                conv.current_state = State.ACTION_PENDING
            elif stage == ConversationStage.ENDED:
                conv.current_state = State.STOPPED
                conv.is_active = False
            return True

    def update_conversation_state(
        self, conversation_id: str, state: State
    ) -> bool:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return False
            conv.set_state(state)
            return True

    def transition_conversation(
        self,
        conversation_id: str,
        user_intent: IntentType,
        message: str = "",
        context_data: Optional[Dict[str, Any]] = None,
        is_proactive_send: bool = False,
    ) -> TransitionResult:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                raise ValueError(f"Conversation not found: {conversation_id}")

            # Assemble current context data if not provided
            if context_data is None:
                context_data = {}
                merchant = self.get_merchant(conv.merchant_id)
                if merchant:
                    context_data["merchant"] = merchant.model_dump()
                    cat = self.get_category(merchant.category_slug)
                    if cat:
                        context_data["category"] = cat.model_dump()
                if conv.customer_id:
                    cust = self.get_customer(conv.customer_id)
                    if cust:
                        context_data["customer"] = cust.model_dump()

            # Record message for repetition detection
            if message and not is_proactive_send:
                conv.record_inbound_message(message)

            inp = TransitionInput(
                current_state=conv.current_state,
                user_intent=user_intent,
                raw_message=message,
                turn_number=len(conv.turns) + 1,
                auto_reply_count=conv.auto_reply_count,
                consecutive_repeated_messages=conv.consecutive_repeated_messages,
                context_data=context_data,
                is_proactive_send=is_proactive_send,
            )

            result = self.state_machine.evaluate_transition(inp)
            if result.valid:
                conv.set_state(result.to_state)
                if result.context_updates_applied:
                    conv.metadata.update(result.context_updates_applied)

            return result

    def increment_auto_reply_count(self, conversation_id: str) -> int:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return 0
            conv.auto_reply_count += 1
            return conv.auto_reply_count

    def reset_auto_reply_count(self, conversation_id: str):
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                conv.auto_reply_count = 0

    # =========================================================================
    # TEARDOWN & RESET
    # =========================================================================

    def clear(self):
        """Wipes all state for clean test runs."""
        with self._lock:
            self._categories.clear()
            self._merchants.clear()
            self._customers.clear()
            self._triggers.clear()
            self._conversations.clear()
            self.conversation_store.clear()
            self.provenance.clear()
