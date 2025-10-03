#!/usr/bin/env python3
"""
Script to automatically add CSRF token support to appointment API tests.

This script updates test function signatures and adds CSRF token generation
for all POST, PUT, PATCH, and DELETE requests in test_appointment_api.py.
"""

import re


def add_csrf_fixtures_to_signature(signature: str) -> str:
    """Add test_user_ws1 and redis_client to function signature if missing."""
    # Check if already has redis_client
    if "redis_client" in signature:
        return signature

    # Find the closing parenthesis before the colon
    # Insert before the closing paren
    if "test_user_ws1" not in signature:
        signature = signature.replace("):", ", test_user_ws1: User,):")
    if "redis_client" not in signature:
        signature = signature.replace("):", ", redis_client,):")

    # Clean up any double commas
    signature = signature.replace(",,", ",")

    return signature


def add_csrf_to_request(content: str, line_num: int, indent: str) -> tuple[str, int]:
    """
    Add CSRF token generation before a request.

    Returns: (modified content, number of lines added)
    """
    csrf_code = f'''{indent}# Add CSRF token for state-changing request
{indent}csrf_headers = await add_csrf_to_client(
{indent}    client, workspace_1.id, test_user_ws1.id, redis_client
{indent})
{indent}
'''
    lines = content.split('\n')
    lines.insert(line_num, csrf_code.rstrip('\n'))
    return '\n'.join(lines), csrf_code.count('\n')


def update_headers_line(line: str) -> str:
    """Update a line that sets headers to include CSRF headers."""
    if "headers =" in line and "get_auth_headers" in line:
        # This is the line that sets headers
        # We need to add headers.update(csrf_headers) after it
        return line  # We'll handle this in the main loop
    return line


def process_test_file(filepath: str) -> None:
    """Process the test file and add CSRF support."""
    with open(filepath, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    modified_lines = []
    i = 0
    in_async_def = False
    current_function_needs_csrf = False
    csrf_already_added = False
    current_indent = ""

    while i < len(lines):
        line = lines[i]

        # Check if this is an async def line
        if line.strip().startswith("async def test_"):
            in_async_def = True
            csrf_already_added = False

            # Check if function signature needs updating
            # Look ahead to find the complete signature (might span multiple lines)
            signature_lines = [line]
            j = i + 1
            while j < len(lines) and "):" not in lines[j]:
                signature_lines.append(lines[j])
                j += 1
            if j < len(lines):
                signature_lines.append(lines[j])

            full_signature = '\n'.join(signature_lines)

            # Update signature if it doesn't have our fixtures
            if "test_user_ws1" not in full_signature or "redis_client" not in full_signature:
                updated_signature = add_csrf_fixtures_to_signature(full_signature)
                # Replace the signature lines
                for sig_line in updated_signature.split('\n'):
                    modified_lines.append(sig_line)
                i = j + 1
                continue

        # Detect when we're about to make a POST/PUT/PATCH/DELETE request
        if in_async_def and ("await client.post(" in line or
                             "await client.put(" in line or
                             "await client.patch(" in line or
                             "await client.delete(" in line):

            # Don't add CSRF if already added for this function
            if not csrf_already_added:
                # Get the indentation
                current_indent = line[:len(line) - len(line.lstrip())]

                # Look back to find where headers are set
                # We want to add CSRF after headers = get_auth_headers()
                for k in range(len(modified_lines) - 1, max(0, len(modified_lines) - 20), -1):
                    prev_line = modified_lines[k]
                    if "headers = get_auth_headers" in prev_line:
                        # Add CSRF code after this line
                        csrf_code = f'''{current_indent}csrf_headers = await add_csrf_to_client(
{current_indent}    client, workspace_1.id, test_user_ws1.id, redis_client
{current_indent})
{current_indent}headers.update(csrf_headers)
'''
                        # Insert after the headers = line
                        modified_lines.insert(k + 1, csrf_code.rstrip('\n'))
                        csrf_already_added = True
                        break

        modified_lines.append(line)
        i += 1

    # Write back
    with open(filepath, 'w') as f:
        f.write('\n'.join(modified_lines))

    print(f"Updated {filepath}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = "tests/test_appointment_api.py"

    process_test_file(filepath)
    print("Done!")
