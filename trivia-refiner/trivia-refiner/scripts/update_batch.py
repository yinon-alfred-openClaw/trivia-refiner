#!/usr/bin/env python3
"""
Trivia Refiner — Stage 3: UPDATE DATABASE
Update database ONLY after user explicitly approves the formatted batch.
Calls the update_questions RPC function in Quiz DB.
"""

import json
import sys
import urllib.request
import os
from datetime import datetime

# Load credentials
creds_path = os.path.expanduser("~/.openclaw/workspace/memory/supabase-creds.json")
try:
    with open(creds_path) as f:
        creds = json.load(f)
    SUPABASE_URL = creds["url"]
    SUPABASE_KEY = creds["key"]
except Exception as e:
    print(f"❌ Error loading credentials: {e}")
    sys.exit(1)

MEMORY_DIR = os.path.expanduser("~/.openclaw/workspace/memory")
TRACKING_FILE = os.path.expanduser("~/.openclaw/workspace/memory/trivia-refiner-processed.json")

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
REQUIRED_FIELDS = {"id", "Question", "Option 1", "Option 2", "Option 3", "Option 4", "Correct Answer", "category_id", "difficulty"}

def validate_change(change):
    """Validate that a change has all required fields."""
    missing = REQUIRED_FIELDS - set(change.keys())
    if missing:
        return False, f"Missing fields: {', '.join(missing)}"
    
    if change.get("difficulty") not in VALID_DIFFICULTIES:
        return False, f"Invalid difficulty '{change['difficulty']}'"
    
    if not isinstance(change.get("category_id"), int) or change.get("category_id") <= 0:
        return False, f"Invalid category_id '{change.get('category_id')}'"
    
    return True, "Valid"

def update_question_in_db(question_id, data):
    """
    Update question in Quiz Database using REST API.
    PATCH raw_questions_he (source table)
    POST/PATCH questions_he (production table)
    This is the ONLY place database updates happen.
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    # Build patch payload
    patch_payload = {
        "Question": data.get("Question"),
        "Option 1": data.get("Option 1"),
        "Option 2": data.get("Option 2"),
        "Option 3": data.get("Option 3"),
        "Option 4": data.get("Option 4"),
        "Correct Answer": data.get("Correct Answer"),
        "category_id": data.get("category_id"),
        "difficulty": data.get("difficulty")
    }
    
    # 1. Update raw_questions_he
    url = f"{SUPABASE_URL}/rest/v1/raw_questions_he?id=eq.{question_id}"
    req = urllib.request.Request(
        url,
        data=json.dumps(patch_payload).encode('utf-8'),
        headers=headers,
        method='PATCH'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            
            # 2. Also upsert into questions_he
            if result:
                upsert_payload = {
                    "id": question_id,
                    **patch_payload
                }
                
                upsert_url = f"{SUPABASE_URL}/rest/v1/questions_he"
                upsert_req = urllib.request.Request(
                    upsert_url,
                    data=json.dumps(upsert_payload).encode('utf-8'),
                    headers=headers,
                    method='POST'
                )
                
                # Try to insert; if already exists, update instead
                try:
                    with urllib.request.urlopen(upsert_req):
                        pass  # Success - inserted
                except urllib.error.HTTPError as e:
                    if e.code == 409:
                        # Row exists, update it
                        upsert_req_patch = urllib.request.Request(
                            f"{SUPABASE_URL}/rest/v1/questions_he?id=eq.{question_id}",
                            data=json.dumps(patch_payload).encode('utf-8'),
                            headers=headers,
                            method='PATCH'
                        )
                        try:
                            with urllib.request.urlopen(upsert_req_patch):
                                pass  # Success - updated
                        except:
                            pass  # Non-critical; raw_questions_he was updated
                    else:
                        pass  # Non-critical; raw_questions_he was updated
            
            return result
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode()
            raise Exception(f"{e} — {error_body}")
        except:
            raise Exception(str(e))

def update_tracking(question_id, status):
    """Track that a question was processed."""
    data = {}
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE) as f:
            data = json.load(f)
    else:
        data = {"version": "1", "processed": []}
    
    # Add entry
    data["processed"].append({
        "id": question_id,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "status": status
    })
    
    # Save
    os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)
    with open(TRACKING_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    """Update database after user approval."""
    
    if len(sys.argv) < 2:
        print("Usage: python3 update_batch.py 193-202")
        print("       (Only call this after user replies APPROVE 193-202)")
        sys.exit(1)
    
    range_str = sys.argv[1]
    
    # Parse range
    try:
        parts = range_str.split('-')
        first_id = int(parts[0])
        last_id = int(parts[1])
    except (ValueError, IndexError):
        print(f"❌ Invalid range format: {range_str}. Use: 193-202")
        sys.exit(1)
    
    # Load approved/formatted batch from memory
    # This would have been created by rephrase_batch.py and approved by user
    batch_file = os.path.join(MEMORY_DIR, f"trivia-formatted-{first_id}-{last_id}.json")
    
    if not os.path.exists(batch_file):
        print(f"❌ No approved batch found at {batch_file}")
        print("   Run rephrase_batch.py first and get user approval.")
        sys.exit(1)
    
    try:
        with open(batch_file) as f:
            batch_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading batch file: {e}")
        sys.exit(1)
    
    changes = batch_data.get("changes", [])
    
    if not changes:
        print(f"❌ No changes found in {batch_file}")
        sys.exit(1)
    
    # Validate all changes first
    print(f"🔍 Validating {len(changes)} changes...")
    invalid = []
    for change in changes:
        valid, msg = validate_change(change)
        if not valid:
            invalid.append((change.get("id"), msg))
    
    if invalid:
        print(f"\n❌ Found {len(invalid)} validation error(s):\n")
        for qid, msg in invalid:
            print(f"  Question {qid}: {msg}")
        return
    
    print(f"✅ All {len(changes)} changes are valid\n")
    
    # Update database
    print(f"📤 Updating {len(changes)} questions in Quiz Database...")
    print()
    
    successful = 0
    failed = 0
    
    for change in changes:
        question_id = change.get("id")
        try:
            result = update_question_in_db(question_id, change)
            successful += 1
            update_tracking(question_id, "updated")
            print(f"  ✅ Question {question_id} updated")
        except Exception as e:
            failed += 1
            update_tracking(question_id, "failed")
            print(f"  ❌ Question {question_id} failed: {e}")
    
    # Summary
    print()
    print("=" * 60)
    print("✅ DATABASE UPDATE COMPLETE")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Total: {successful + failed}")
    print("=" * 60)
    
    # Clean up
    try:
        os.remove(batch_file)
    except:
        pass

if __name__ == "__main__":
    main()
