"""
Deduplication and Master Data Entity Resolution.
Finds duplicate or variant SKUs across manufacturer descriptions.
"""

from __future__ import annotations
from dataclasses import dataclass
import re

from models import CleanRow


@dataclass
class DuplicateMatch:
    sku_a: str
    desc_a: str
    sku_b: str
    desc_b: str
    similarity_score: float
    match_reason: str
    recommended_master: str


def find_duplicates(rows: list[CleanRow]) -> list[DuplicateMatch]:
    """
    Identifies duplicate product pairs based on normalized description tokens
    and brand/manufacturer matching.
    """
    matches: list[DuplicateMatch] = []
    
    # Tokenizer helper
    def tokenize(text: str) -> set[str]:
        words = re.findall(r"\b[a-z0-9]+\b", text.lower())
        return {w for w in words if len(w) > 1}

    n = len(rows)
    for i in range(n):
        for j in range(i + 1, n):
            r1 = rows[i]
            r2 = rows[j]
            
            # Same part number but different description
            if r1.mfg_part_num == r2.mfg_part_num and r1.part_desc != r2.part_desc:
                matches.append(
                    DuplicateMatch(
                        sku_a=r1.mfg_part_num,
                        desc_a=r1.part_desc,
                        sku_b=r2.mfg_part_num,
                        desc_b=r2.part_desc,
                        similarity_score=1.0,
                        match_reason="Identical Manufacturer Part Number",
                        recommended_master=f"{r1.mfg_part_num} (Canonical)",
                    )
                )
                continue
            
            # High Jaccard similarity in description
            t1 = tokenize(r1.part_desc)
            t2 = tokenize(r2.part_desc)
            if not t1 or not t2:
                continue
                
            intersection = t1 & t2
            union = t1 | t2
            jaccard = len(intersection) / len(union)
            
            if jaccard >= 0.80 and r1.mfg_part_num != r2.mfg_part_num:
                longer_desc = r1.mfg_part_num if len(r1.part_desc) >= len(r2.part_desc) else r2.mfg_part_num
                matches.append(
                    DuplicateMatch(
                        sku_a=r1.mfg_part_num,
                        desc_a=r1.part_desc,
                        sku_b=r2.mfg_part_num,
                        desc_b=r2.part_desc,
                        similarity_score=round(jaccard, 2),
                        match_reason=f"High description overlap ({round(jaccard*100)}% token match)",
                        recommended_master=longer_desc,
                    )
                )
                
    return matches
