#!/usr/bin/env python3
"""
Seed internal incident runbooks from the runbooks/ directory into PostgreSQL pgvector knowledge base.
Run directly: python scripts/seed_rag.py
"""

import os
import re
import sys
from typing import List, Dict, Any

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.repositories import IncidentDocRepository
from app.tools.rag import generate_embedding
from app.config import settings


def split_markdown_into_chunks(content: str, source_path: str, service: str) -> List[Dict[str, Any]]:
    """
    Split markdown document into logical chunks based on sections/headers (##),
    preserving the top-level title and section header for semantic clarity.
    """
    chunks = []
    lines = content.splitlines()

    doc_title = ""
    current_section = "Overview"
    current_lines: List[str] = []

    for line in lines:
        if line.startswith("# ") and not doc_title:
            doc_title = line.strip("# ").strip()
            continue

        if line.startswith("## "):
            if current_lines:
                chunk_text = f"Document: {doc_title}\nSection: {current_section}\n" + "\n".join(current_lines).strip()
                if len(chunk_text.strip()) > 30:
                    chunks.append({
                        "content": chunk_text,
                        "metadata": {
                            "service": service,
                            "category": "runbook",
                            "source": source_path,
                            "section": current_section,
                            "title": doc_title
                        }
                    })
                current_lines = []
            current_section = line.strip("# ").strip()
            continue

        current_lines.append(line)

    if current_lines:
        chunk_text = f"Document: {doc_title}\nSection: {current_section}\n" + "\n".join(current_lines).strip()
        if len(chunk_text.strip()) > 30:
            chunks.append({
                "content": chunk_text,
                "metadata": {
                    "service": service,
                    "category": "runbook",
                    "source": source_path,
                    "section": current_section,
                    "title": doc_title
                }
            })

    return chunks


def seed_runbooks(force: bool = False):
    """Scan the runbooks/ directory, generate embeddings, and insert into incident_docs."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "runbooks"))
    if not os.path.exists(base_dir):
        print(f"[X] Runbooks directory not found at: {base_dir}")
        return

    print(f"[*] Scanning runbooks in {base_dir}...")
    total_files = 0
    total_chunks = 0
    skipped_files = 0

    for root, _, files in os.walk(base_dir):
        for file in files:
            if not file.endswith(".md"):
                continue

            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
            service = rel_path.split("/")[0] if "/" in rel_path else "general"

            if not force and IncidentDocRepository.doc_exists_for_source(rel_path):
                print(f"[-] Skipping already seeded runbook: {rel_path}")
                skipped_files += 1
                continue

            total_files += 1
            print(f"[*] Processing runbook: {rel_path} (service: {service})")

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            chunks = split_markdown_into_chunks(content, rel_path, service)

            for chunk in chunks:
                emb = generate_embedding(chunk["content"])
                IncidentDocRepository.insert(
                    content=chunk["content"],
                    metadata=chunk["metadata"],
                    embedding=emb
                )
                total_chunks += 1

    print(f"[+] Seeding complete: {total_files} files processed, {total_chunks} chunks stored, {skipped_files} skipped.")
    print(f"[+] Total documents in knowledge base: {IncidentDocRepository.count()}")


if __name__ == "__main__":
    force_run = "--force" in sys.argv
    seed_runbooks(force=force_run)
