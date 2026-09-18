"""Populates a fresh database with demo data: one account per role, the
workflow_rules from FLOWFORGE_SPEC.md's rule engine examples, and a spread
of sample requests covering every processing outcome the pipeline can reach.

Run with:  python -m app.seed   (from backend/, with DATABASE_URL pointing at
a migrated database — this does not run migrations itself).

Safe to re-run: skips creating anything whose identifying field already
exists (email for users, name for rules), so running it twice won't
duplicate data.
"""
from app.ai.providers.mock import MockAIProvider
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.request import ProcessingStatus, Request, RequestStatus
from app.models.user import User, UserRole
from app.models.workflow_rule import WorkflowRule
from app.services import processing_service

DEMO_PASSWORD = "password123"

USERS = [
    {"name": "Ada Admin", "email": "admin@flowforge.dev", "role": UserRole.ADMIN},
    {"name": "Owen Operator", "email": "operator@flowforge.dev", "role": UserRole.OPERATOR},
    {"name": "Uma User", "email": "user@flowforge.dev", "role": UserRole.USER},
    {"name": "Priya Patel", "email": "priya@flowforge.dev", "role": UserRole.USER},
    {"name": "Marcus Chen", "email": "marcus@flowforge.dev", "role": UserRole.USER},
]

# Directly implements FLOWFORGE_SPEC.md section 8's rule examples, plus the
# section 7 default category -> team routing table. Order matters only in
# that default routing rules are seeded before their overrides — the rule
# engine's actual conflict resolution (see app/rules/engine.py) doesn't
# depend on insertion order beyond that.
RULES = [
    # Default category routing (spec section 7)
    {"name": "Default IT Support Routing", "category": "IT_SUPPORT", "condition": "category == IT_SUPPORT", "action": "assign_team = IT Team"},
    {"name": "Default HR Routing", "category": "HR", "condition": "category == HR", "action": "assign_team = HR Team"},
    {"name": "Default Finance Routing", "category": "FINANCE", "condition": "category == FINANCE", "action": "assign_team = Finance Team"},
    {"name": "Default Procurement Routing", "category": "PROCUREMENT", "condition": "category == PROCUREMENT", "action": "assign_team = Procurement Team"},
    {"name": "Default Customer Service Routing", "category": "CUSTOMER_SERVICE", "condition": "category == CUSTOMER_SERVICE", "action": "assign_team = Customer Success Team"},
    {"name": "Default General Routing", "category": "GENERAL", "condition": "category == GENERAL", "action": "assign_team = General Support Team"},
    # Access requests need a higher confidence bar before routing to security (spec section 8)
    {"name": "Access Request Routing", "category": "ACCESS_REQUEST", "condition": "category == ACCESS_REQUEST AND confidence >= 0.80", "action": "assign_team = IT Security Team"},
    # Cross-category overrides (spec section 8)
    {"name": "Low Confidence Manual Review", "category": None, "condition": "confidence < 0.70", "action": "status = MANUAL_REVIEW"},
    {"name": "High Priority Urgent Handling", "category": None, "condition": "priority == HIGH", "action": "mark_urgent = true"},
    {"name": "Finance Missing Amount", "category": "FINANCE", "condition": "amount IS NULL", "action": "status = NEEDS_INFORMATION"},
    {"name": "Finance Approval Threshold", "category": "FINANCE", "condition": "category == FINANCE AND amount > 100000", "action": "require_approval = true"},
]

# (title, description, department, requester_email, process_immediately)
SAMPLE_REQUESTS = [
    ("Cannot access git repository", "I just joined engineering yesterday and cannot access the internal git repository. My login is not working.", "Engineering", "priya@flowforge.dev", True),
    ("Need VPN access for remote work", "I am starting a remote work arrangement and need VPN access configured on my laptop.", "Engineering", "marcus@flowforge.dev", True),
    ("Laptop keeps crashing", "My work laptop crashes several times a day, I think it needs a hardware or software fix.", "Engineering", "priya@flowforge.dev", True),
    ("Wifi not working in office", "The office wifi network has been down all morning on the 3rd floor.", "Operations", "marcus@flowforge.dev", True),
    ("Request for parental leave", "I would like to request parental leave starting next month, please advise on the process.", "People", "priya@flowforge.dev", True),
    ("Question about benefits enrollment", "I have a question about the open enrollment period for health benefits.", "People", "marcus@flowforge.dev", True),
    ("Reimbursement for conference travel", "I paid $4500 out of pocket for flights and hotel for a conference and need to be reimbursed.", "Sales", "priya@flowforge.dev", True),
    ("Approval for new equipment purchase", "We need to purchase new servers for the data center, total cost is $250000.", "Engineering", "marcus@flowforge.dev", True),
    ("Expense report submission", "I need to submit my expense report for last month but I am not sure of the process.", "Sales", "priya@flowforge.dev", True),
    ("New vendor onboarding for office supplies", "We would like to onboard a new vendor for office supplies, please advise on procurement steps.", "Operations", "marcus@flowforge.dev", True),
    ("Purchase order for new laptops", "Requesting a purchase order and vendor quote for 20 new laptops for the engineering team.", "Engineering", "priya@flowforge.dev", True),
    ("Customer complaint about delayed shipment", "A customer has complained that their shipment was delayed by two weeks with no notice.", "Support", "marcus@flowforge.dev", True),
    ("Refund request from unhappy client", "A client is requesting a refund due to being unhappy with the service provided.", "Support", "priya@flowforge.dev", True),
    ("General question about office hours", "What are the standard office hours for the downtown location?", "Operations", "marcus@flowforge.dev", True),
    ("Unclear request needs follow-up", "Something about the thing from last week, not sure who to contact about it.", "Operations", "priya@flowforge.dev", True),
    ("Production is down, urgent", "Production database is completely down and blocked, this is urgent and needs immediate attention.", "Engineering", "marcus@flowforge.dev", True),
    ("Access to shared drive", "I need access to the shared engineering drive for a new project.", "Engineering", "priya@flowforge.dev", False),
    ("New request just submitted", "This request was just submitted and has not been processed by the pipeline yet.", "Sales", "marcus@flowforge.dev", False),
]


def get_or_create_user(db, *, name: str, email: str, role: UserRole) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        return user
    user = User(name=name, email=email, password_hash=hash_password(DEMO_PASSWORD), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_rule(db, *, name: str, category: str | None, condition: str, action: str) -> WorkflowRule:
    rule = db.query(WorkflowRule).filter(WorkflowRule.name == name).first()
    if rule is not None:
        return rule
    rule = WorkflowRule(name=name, category=category, condition=condition, action=action, enabled=True)
    db.add(rule)
    db.commit()
    return rule


def seed() -> None:
    db = SessionLocal()
    try:
        print("Seeding users...")
        users_by_email = {u["email"]: get_or_create_user(db, **u) for u in USERS}

        print("Seeding workflow rules...")
        for rule in RULES:
            get_or_create_rule(db, **rule)

        print("Seeding sample requests...")
        provider = MockAIProvider()
        created = 0
        for title, description, department, requester_email, process_immediately in SAMPLE_REQUESTS:
            existing = db.query(Request).filter(Request.title == title).first()
            if existing is not None:
                continue

            requester = users_by_email[requester_email]
            request = Request(
                requester_id=requester.id,
                title=title,
                description=description,
                department=department,
                status=RequestStatus.PENDING,
                processing_status=ProcessingStatus.QUEUED,
            )
            db.add(request)
            db.commit()
            db.refresh(request)
            created += 1

            if process_immediately:
                # Runs the real pipeline synchronously (no Celery/Redis needed
                # for seeding) — the same processing_service.run_pipeline a
                # Celery worker calls, just invoked directly here.
                processing_service.run_pipeline(db, request.id, ai_provider=provider)

        print(f"Done. {len(users_by_email)} users, {len(RULES)} rules, {created} new requests.")
        print(f"Demo login password for all seeded users: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
