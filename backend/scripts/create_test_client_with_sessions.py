#!/usr/bin/env python3
"""
Create Test Client with Sessions for AI Agent Testing

This script creates a realistic client profile with medical history and 3 SOAP session notes
to test the AI agent functionality.

Usage:
    cd backend
    env PYTHONPATH=src uv run python scripts/create_test_client_with_sessions.py <workspace_id>
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.workspace import Workspace


async def create_test_client_with_sessions(workspace_id: str):
    """Create a test client with medical history and 3 session notes."""
    async with AsyncSessionLocal() as db:
        # Verify workspace exists
        result = await db.execute(
            select(Workspace).where(Workspace.id == uuid.UUID(workspace_id))
        )
        workspace = result.scalar_one_or_none()

        if not workspace:
            print(f"❌ Workspace {workspace_id} not found")
            return

        print(f"✅ Found workspace: {workspace.name}")

        # Create client
        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Sarah",
            last_name="Cohen",
            email="sarah.cohen@example.com",
            phone="054-123-4567",
            date_of_birth=None,  # Skip date_of_birth to avoid encryption issues
            address="15 Dizengoff St, Tel Aviv",
            medical_history=(
                "Patient is a 38-year-old office worker with chronic lower back pain. "
                "History of L5-S1 disc herniation diagnosed 2 years ago via MRI. "
                "Previous treatments include physical therapy (6 months), NSAIDs, and "
                "chiropractic adjustments with moderate success. Pain worsens with "
                "prolonged sitting and improves with walking. No history of surgery. "
                "Occasional right leg radiculopathy. Non-smoker, moderate exercise "
                "(yoga 2x/week when pain permits). No allergies. No current medications."
            ),
            emergency_contact_name="David Cohen",
            emergency_contact_phone="052-987-6543",
            consent_status=True,
            is_active=True,
            notes="Prefers morning appointments. Responsive to soft tissue work.",
            tags=["chronic-pain", "office-worker", "yoga-enthusiast"],
        )
        db.add(client)
        await db.flush()

        print(f"\n✅ Created client: {client.first_name} {client.last_name}")
        print(f"   Client ID: {client.id}")
        print(f"   Medical History: {client.medical_history[:100]}...")

        # Create Session 1 (3 weeks ago - Initial assessment)
        session1_date = datetime.now() - timedelta(weeks=3)
        session1 = Session(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            session_date=session1_date,
            duration_minutes=60,
            subjective=(
                "Patient reports sharp lower back pain (7/10) radiating down right leg "
                "to knee. Pain started 2 weeks ago after moving heavy boxes at work. "
                "Describes pain as 'shooting and burning' especially when sitting for "
                "more than 20 minutes. Morning stiffness lasts about 30 minutes. "
                "Difficulty bending forward and putting on shoes. Sleep disrupted - "
                "wakes 2-3 times per night when rolling over. Has been taking ibuprofen "
                "400mg TID with minimal relief. Unable to attend yoga classes. "
                "Patient appears anxious about the flare-up."
            ),
            objective=(
                "Observation: Antalgic gait favoring right side. Reduced lumbar lordosis. "
                "Tender to palpation over L4-L5, L5-S1 paraspinals bilaterally (right > left). "
                "ROM: Flexion 40° (limited by pain), extension 15° (limited), lateral flexion "
                "20° bilateral. Positive straight leg raise test at 35° on right (reproduces "
                "leg pain). Negative on left. Decreased sensation in L5 dermatome (lateral calf). "
                "Muscle testing: 4/5 weakness in right ankle dorsiflexion. Deep tendon reflexes "
                "intact. No saddle anesthesia. Myofascial trigger points in right piriformis "
                "and quadratus lumborum."
            ),
            assessment=(
                "Acute exacerbation of chronic L5-S1 radiculopathy with right lower extremity "
                "radicular symptoms. Likely disc re-herniation vs significant inflammation. "
                "Moderate functional limitation (ODI 52%). Red flags ruled out (no cauda equina "
                "symptoms, no progressive neurological deficit). Contributing factors: prolonged "
                "sitting, poor lifting mechanics, deconditioning from pain avoidance. "
                "Psychological: mild anxiety related to pain and work demands."
            ),
            plan=(
                "1. Manual therapy: gentle myofascial release to lumbar paraspinals, piriformis, "
                "QL. Grade II-III lumbar mobilizations. 2. Modalities: ice 15min post-treatment. "
                "3. Patient education: proper sitting posture, frequent position changes, "
                "avoid forward bending for 2 weeks. 4. Home exercise: gentle nerve flossing "
                "(sciatic), prone extensions (McKenzie), pelvic tilts. 5. Recommend follow-up "
                "with physician if no improvement in 2 weeks for possible MRI and medication review. "
                "6. Return visit in 3-4 days. 7. Short-term goal: reduce pain from 7/10 to 4/10 "
                "within 2 weeks. Long-term: return to yoga within 6 weeks."
            ),
        )
        db.add(session1)

        # Create Session 2 (2 weeks ago - Follow-up)
        session2_date = datetime.now() - timedelta(weeks=2)
        session2 = Session(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            session_date=session2_date,
            duration_minutes=45,
            subjective=(
                "Patient reports improvement in pain intensity (now 5/10 vs previous 7/10). "
                "Leg pain reduced significantly - only mild tingling to mid-calf. "
                "Morning stiffness down to 10-15 minutes. Sleep improved - only waking once per night. "
                "Back pain still present with prolonged sitting (>30 min) but more manageable. "
                "Able to put on shoes with less difficulty. Started doing home exercises daily. "
                "Decreased ibuprofen to 200mg BID. Patient reports feeling more optimistic. "
                "Concern: slight increase in pain after attempting to return to desk work yesterday."
            ),
            objective=(
                "Observation: Improved gait pattern, less antalgic posture. Better lumbar curve. "
                "Palpation: Reduced tenderness L5-S1 area (moderate vs severe). ROM: Flexion improved "
                "to 60° (still limited), extension 20°, lateral flexion 25° bilateral. "
                "Straight leg raise: 50° on right (vs 35° previous - improved), negative left. "
                "Sensation: L5 dermatome hypesthesia resolving (patient reports 'feels almost normal'). "
                "Muscle testing: Improved to 4+/5 ankle dorsiflexion. Piriformis trigger points "
                "reduced. QL still tender but less reactive."
            ),
            assessment=(
                "Subacute L5-S1 radiculopathy showing positive response to conservative treatment. "
                "Significant improvement in radicular symptoms (leg pain/paresthesia). "
                "Axial back pain persisting, likely mechanical and myofascial in nature. "
                "Functional improvement (ODI estimated 35%, down from 52%). "
                "Work ergonomics remain a concern - patient attempted 6-hour desk shift "
                "which increased symptoms. Good compliance with home exercise program. "
                "Prognosis: favorable for continued recovery with activity modification."
            ),
            plan=(
                "1. Continue manual therapy: deeper soft tissue work now tolerated. "
                "Grade III-IV lumbar mobilizations. 2. Progress home exercises: add bird-dog, "
                "dead-bug exercises for core stability. Continue nerve flossing. "
                "3. Ergonomic assessment: recommend standing desk trial, lumbar roll for car/office. "
                "4. Gradual return to work: suggest 4-hour shifts initially, increase by 1 hour weekly. "
                "5. Begin gentle stretching: hamstrings, hip flexors (avoid aggressive stretching). "
                "6. Hold on yoga classes for 2 more weeks, then trial gentle/restorative class. "
                "7. Follow-up in 1 week. 8. Defer MD referral - good progress without medications."
            ),
        )
        db.add(session2)

        # Create Session 3 (1 week ago - Progress check)
        session3_date = datetime.now() - timedelta(weeks=1)
        session3 = Session(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            session_date=session3_date,
            duration_minutes=45,
            subjective=(
                "Patient reports continued improvement. Pain now 3/10, mostly localized to lower back. "
                "No leg pain or numbness for past 4 days. Morning stiffness minimal (<5 minutes). "
                "Sleeping through the night consistently. Returned to work with modified schedule "
                "(5 hours/day) without significant pain increase. Using standing desk alternating "
                "with sitting every 30-45 minutes. Completed home exercises 6 days this week. "
                "Excited to report: walked 3km yesterday with no pain during or after. "
                "Main complaint now: residual tightness in right hip and lower back, especially "
                "end of workday. Patient asking when she can return to yoga."
            ),
            objective=(
                "Observation: Normal gait, restored lumbar lordosis. Posture improved. "
                "Palpation: Minimal tenderness L5-S1 paraspinals. No trigger points in piriformis. "
                "Mild tightness in QL bilateral. ROM: Flexion 80° (near normal), extension 25°, "
                "lateral flexion 30° (full ROM). Straight leg raise: 70° bilateral, no pain. "
                "Sensation: Normal in all dermatomes. Muscle testing: 5/5 throughout lower extremities. "
                "Deep tendon reflexes normal and symmetric. Core stability testing: able to maintain "
                "plank 45 seconds, bird-dog with good form."
            ),
            assessment=(
                "Resolution of acute L5-S1 radiculopathy. Residual mild mechanical low back pain "
                "related to prolonged postures and myofascial tightness. Excellent functional recovery "
                "(estimated ODI <20%). Patient demonstrating good body mechanics and self-management "
                "strategies. Core stability improved but not yet optimal. No neurological deficits. "
                "Ready for gradual return to full activities with continued home program. "
                "Prognosis: excellent for full return to pre-injury status."
            ),
            plan=(
                "1. Manual therapy: focus on residual myofascial restrictions (QL, hip flexors). "
                "Grade IV lumbar mobilizations for end-range mobility. 2. Progress strengthening: "
                "add bridges, side plank progressions, bird-dog with resistance. "
                "3. Clearance for gentle yoga: recommend starting with 1 restorative class this week, "
                "avoiding deep forward folds and twists initially. Progress to regular classes "
                "over 2-3 weeks based on tolerance. 4. Work: cleared for full-time hours, continue "
                "ergonomic setup. 5. Prevention education: proper lifting mechanics, regular breaks, "
                "maintain exercise routine. 6. Transition to maintenance: follow-up PRN or monthly "
                "check-ins. 7. Provide written home program progression. 8. Advise to return immediately "
                "if leg symptoms recur. Success: patient met short-term goal (pain <4/10) and on track "
                "for long-term goal (return to yoga)."
            ),
        )
        db.add(session3)

        await db.commit()

        print(f"\n✅ Created 3 sessions:")
        print(f"   Session 1: {session1.session_date} (Initial - acute flare-up)")
        print(f"   Session 2: {session2.session_date} (Follow-up - improving)")
        print(f"   Session 3: {session3.session_date} (Progress - near resolution)")

        print("\n🎉 Test data creation complete!")
        print("\nNext steps:")
        print("1. Wait ~5 seconds for background embeddings to be generated")
        print("2. Go to http://localhost:5173/")
        print("3. Log in with your account")
        print("4. Navigate to the AI Agent interface")
        print("5. Try these test queries:")
        print("   - 'When did Sarah's back pain start?'")
        print("   - 'What treatments helped Sarah the most?'")
        print("   - 'Did Sarah have any leg pain?'")
        print("   - 'What is Sarah's medical history?'")
        print("   - 'Is Sarah ready to return to yoga?'")
        print("   - 'מתי התחילו הכאבים של שרה?' (Hebrew)")
        print(f"\n📊 Client Details:")
        print(f"   Name: {client.first_name} {client.last_name}")
        print(f"   Client ID: {client.id}")
        print(f"   Workspace ID: {workspace.id}")

        return {
            "client_id": str(client.id),
            "session_ids": [str(session1.id), str(session2.id), str(session3.id)],
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_test_client_with_sessions.py <workspace_id>")
        print("\nTo find your workspace_id, run:")
        print("  docker compose exec db psql -U pazpaz -d pazpaz -c \"SELECT id, name FROM workspaces;\"")
        sys.exit(1)

    workspace_id = sys.argv[1]

    print("Creating test client with sessions...")
    print(f"Workspace ID: {workspace_id}\n")

    result = asyncio.run(create_test_client_with_sessions(workspace_id))
