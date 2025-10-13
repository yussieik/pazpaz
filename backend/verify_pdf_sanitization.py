#!/usr/bin/env python3
"""
Verification script for PDF metadata sanitization.

This script demonstrates that PDF metadata containing PHI is properly stripped
during the file sanitization process.
"""

import io
import sys

from pypdf import PdfReader, PdfWriter

from pazpaz.utils.file_sanitization import strip_pdf_metadata


def create_test_pdf_with_metadata() -> bytes:
    """Create a PDF with PHI-containing metadata for testing."""
    print("Creating test PDF with sensitive metadata...")

    pdf_writer = PdfWriter()
    pdf_writer.add_blank_page(width=612, height=792)  # US Letter size

    # Add metadata that contains PHI (simulating a real-world scenario)
    pdf_writer.add_metadata(
        {
            "/Author": "Dr. Sarah Johnson, PT (Therapist)",
            "/Title": "Treatment Plan - Patient: John Smith (DOB: 1980-05-15)",
            "/Subject": "Physical therapy session notes for lower back pain",
            "/Keywords": "patient, therapy, confidential, PHI, chronic pain, lumbar",
            "/Creator": "PazPaz Practice Management v1.0 - Downtown Clinic",
            "/Producer": "Microsoft Word - Dr. Johnson's Laptop",
            "/CreationDate": "D:20251012143000-05'00'",
            "/ModDate": "D:20251012145500-05'00'",
        }
    )

    output = io.BytesIO()
    pdf_writer.write(output)
    return output.getvalue()


def print_metadata(metadata, label: str):
    """Print PDF metadata in a readable format."""
    print(f"\n{label}:")
    print("-" * 60)
    if metadata:
        for key, value in metadata.items():
            print(f"  {key}: {value}")
    else:
        print("  (No metadata)")
    print("-" * 60)


def main():
    """Run verification test."""
    print("=" * 70)
    print("PDF METADATA SANITIZATION VERIFICATION")
    print("=" * 70)

    # Step 1: Create PDF with PHI metadata
    original_pdf = create_test_pdf_with_metadata()
    print(f"Original PDF size: {len(original_pdf)} bytes")

    # Step 2: Read and display original metadata
    original_reader = PdfReader(io.BytesIO(original_pdf))
    print_metadata(original_reader.metadata, "ORIGINAL METADATA (Contains PHI)")

    # Step 3: Sanitize PDF
    print("\nSanitizing PDF (stripping metadata)...")
    sanitized_pdf = strip_pdf_metadata(original_pdf, "test_consent_form.pdf")
    print(f"Sanitized PDF size: {len(sanitized_pdf)} bytes")

    # Step 4: Read and display sanitized metadata
    sanitized_reader = PdfReader(io.BytesIO(sanitized_pdf))
    print_metadata(sanitized_reader.metadata, "SANITIZED METADATA (PHI Removed)")

    # Step 5: Verify all PHI fields are removed
    print("\nVERIFICATION:")
    print("-" * 60)

    sanitized_metadata = sanitized_reader.metadata
    phi_fields = [
        "/Author",
        "/Title",
        "/Subject",
        "/Keywords",
        "/Creator",
        "/CreationDate",
        "/ModDate",
    ]

    all_removed = True
    for field in phi_fields:
        is_removed = (
            field not in sanitized_metadata or not sanitized_metadata.get(field)
        )
        status = "✓ REMOVED" if is_removed else "✗ STILL PRESENT"
        print(f"  {field}: {status}")
        if not is_removed:
            all_removed = False

    # Check Producer field (pypdf may add its own)
    if "/Producer" in sanitized_metadata:
        producer = sanitized_metadata.get("/Producer")
        if producer == "pypdf":
            print(f"  /Producer: ✓ Safe (pypdf library marker, no PHI)")
        else:
            print(f"  /Producer: ⚠ Contains: {producer}")
            all_removed = False

    # Step 6: Verify page content is preserved
    print("\nCONTENT PRESERVATION:")
    print("-" * 60)
    print(f"  Original page count: {len(original_reader.pages)}")
    print(f"  Sanitized page count: {len(sanitized_reader.pages)}")
    print(
        f"  Pages preserved: {'✓ YES' if len(original_reader.pages) == len(sanitized_reader.pages) else '✗ NO'}"
    )

    # Step 7: Summary
    print("\n" + "=" * 70)
    if all_removed and len(original_reader.pages) == len(sanitized_reader.pages):
        print("✓ VERIFICATION PASSED")
        print("All PHI-containing metadata fields removed successfully!")
        print("PDF content and structure preserved.")
        return 0
    else:
        print("✗ VERIFICATION FAILED")
        print("Some PHI fields were not removed or content was corrupted.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
