"""Script to safely add category_slug fact to vera/context/selector.py."""
from pathlib import Path

file_path = Path("vera/context/selector.py")
content = file_path.read_text(encoding="utf-8")

target = """            if merchant.identity.owner_first_name:"""
replacement = """            if merchant.category_slug:
                mandatory.append(
                    SelectedFact(
                        key="category_slug",
                        value=merchant.category_slug,
                        tier=FactTier.MANDATORY,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="category_slug",
                            value=merchant.category_slug,
                            context_version=mer_ver,
                        ),
                        priority_score=0.98,
                        relevance_reason="Vertical business category alignment",
                    )
                )
                total_considered += 1

            if merchant.identity.owner_first_name:"""

if target not in content:
    print("Target not found in selector.py!")
    exit(1)

content = content.replace(target, replacement, 1)
file_path.write_text(content, encoding="utf-8")
print("Successfully updated vera/context/selector.py!")
