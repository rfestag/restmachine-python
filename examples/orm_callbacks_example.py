"""
Example demonstrating before_save and after_save callbacks in RestMachine ORM.

This example shows how to use decorators to:
1. Automatically update timestamps (before_save)
2. Normalize data (before_save)
3. Implement audit logging (after_save)
4. Send notifications (after_save)
"""

from datetime import datetime
from typing import Optional
from restmachine_orm import Model, Field, before_save, after_save
from restmachine_orm.backends import InMemoryBackend, InMemoryAdapter


# Initialize backend
backend = InMemoryBackend(InMemoryAdapter())


class AuditLog:
    """Simple audit log for demonstration."""
    entries = []

    @classmethod
    def log(cls, action: str, model_name: str, model_id: str, user: str = "system"):
        """Log an audit entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "model": model_name,
            "id": model_id,
            "user": user,
        }
        cls.entries.append(entry)
        print(f"[AUDIT] {action} {model_name} {model_id} by {user}")

    @classmethod
    def clear(cls):
        """Clear the audit log."""
        cls.entries.clear()


class EmailService:
    """Mock email service for demonstration."""
    sent_emails = []

    @classmethod
    def send(cls, to: str, subject: str, body: str):
        """Send an email (mock)."""
        email = {"to": to, "subject": subject, "body": body}
        cls.sent_emails.append(email)
        print(f"[EMAIL] To: {to}, Subject: {subject}")

    @classmethod
    def clear(cls):
        """Clear sent emails."""
        cls.sent_emails.clear()


class User(Model):
    """
    User model with automatic timestamp management and audit logging.

    Demonstrates:
    - before_save: Automatic timestamp updates
    - before_save: Email normalization
    - after_save: Audit logging
    - after_save: Notifications
    """

    class Meta:
        backend = backend

    id: str = Field(primary_key=True)
    email: str = Field(unique=True)
    name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @before_save
    def update_timestamps(self):
        """Automatically update timestamps before saving."""
        now = datetime.now()
        if not self._is_persisted:
            # New record - set created_at
            self.created_at = now
            print(f"[BEFORE_SAVE] Setting created_at for new user: {self.id}")
        else:
            print(f"[BEFORE_SAVE] Updating user: {self.id}")

        # Always update updated_at
        self.updated_at = now

    @before_save
    def normalize_email(self):
        """Normalize email to lowercase before saving."""
        original_email = self.email
        self.email = self.email.lower().strip()
        if original_email != self.email:
            print(f"[BEFORE_SAVE] Normalized email: {original_email} -> {self.email}")

    @after_save
    def audit_log_change(self):
        """Log all changes to audit log."""
        AuditLog.log("SAVE", "User", self.id)

    @after_save
    def send_notification(self):
        """Send notification after save."""
        EmailService.send(
            to=self.email,
            subject="User saved",
            body=f"User {self.name} was saved successfully.",
        )


class BlogPost(Model):
    """
    Blog post model demonstrating version tracking.

    Demonstrates:
    - before_save: Version incrementing
    - after_save: Notification to subscribers
    """

    class Meta:
        backend = backend

    id: str = Field(primary_key=True)
    author_id: str
    title: str
    content: str
    version: int = 0
    published: bool = False
    updated_at: Optional[datetime] = None

    @before_save
    def increment_version(self):
        """Increment version number on each save."""
        if self._is_persisted:
            # Only increment on updates, not creates
            self.version += 1
            print(f"[BEFORE_SAVE] Incrementing post version to {self.version}")

    @before_save
    def update_timestamp(self):
        """Update timestamp."""
        self.updated_at = datetime.now()

    @after_save
    def notify_published(self):
        """Notify subscribers when post is published."""
        if self.published:
            print(f"[AFTER_SAVE] Post is published: {self.title}")
            # In real app: queue notification job

    @after_save
    def log_change(self):
        """Log changes for analytics."""
        AuditLog.log("SAVE", "BlogPost", self.id, user=self.author_id)


def example_1_automatic_timestamps():
    """Example 1: Automatic timestamp management."""
    print("\n" + "=" * 60)
    print("Example 1: Automatic Timestamp Management")
    print("=" * 60)

    # Create a new user
    print("\n1. Creating new user...")
    user = User(id="user-1", email="ALICE@EXAMPLE.COM", name="Alice")
    print(f"   Before save - created_at: {user.created_at}")
    print(f"   Before save - updated_at: {user.updated_at}")

    user.save()

    print(f"   After save - created_at: {user.created_at}")
    print(f"   After save - updated_at: {user.updated_at}")
    print(f"   After save - email: {user.email}")  # Should be normalized

    # Update the user
    print("\n2. Updating user...")
    import time
    time.sleep(0.1)  # Small delay to see timestamp difference

    first_updated_at = user.updated_at
    user.name = "Alice Smith"
    user.save()

    print(f"   Old updated_at: {first_updated_at}")
    print(f"   New updated_at: {user.updated_at}")
    print(f"   Timestamps are different: {user.updated_at != first_updated_at}")


def example_2_audit_logging():
    """Example 2: Automatic audit logging."""
    print("\n" + "=" * 60)
    print("Example 2: Automatic Audit Logging")
    print("=" * 60)

    AuditLog.clear()

    print("\n1. Creating user...")
    user = User.create(id="user-2", email="bob@example.com", name="Bob")

    print("\n2. Updating user...")
    user.name = "Bob Smith"
    user.save()

    print("\n3. Creating another user...")
    User.create(id="user-3", email="carol@example.com", name="Carol")

    print("\n4. Audit log entries:")
    for entry in AuditLog.entries:
        print(f"   {entry['timestamp']}: {entry['action']} {entry['model']} {entry['id']}")


def example_3_notifications():
    """Example 3: Sending notifications on user save."""
    print("\n" + "=" * 60)
    print("Example 3: Notifications on User Save")
    print("=" * 60)

    EmailService.clear()

    print("\n1. Creating new users...")
    User.create(id="user-4", email="dave@example.com", name="Dave")
    User.create(id="user-5", email="eve@example.com", name="Eve")

    print(f"\n2. Notifications sent: {len(EmailService.sent_emails)}")
    for email in EmailService.sent_emails:
        print(f"   To: {email['to']}")
        print(f"   Subject: {email['subject']}")

    print("\n3. Updating existing user (notification sent on update too)...")
    user = User.get(id="user-4")
    user.name = "David"
    user.save()

    print(f"\n4. Total notifications sent: {len(EmailService.sent_emails)}")
    print("   (Should be 3 - notifications sent on every save)")


def example_4_version_tracking():
    """Example 4: Automatic version tracking for blog posts."""
    print("\n" + "=" * 60)
    print("Example 4: Automatic Version Tracking")
    print("=" * 60)

    print("\n1. Creating blog post...")
    post = BlogPost.create(
        id="post-1",
        author_id="user-1",
        title="My First Post",
        content="This is my first blog post!",
    )
    print(f"   Initial version: {post.version}")

    print("\n2. Updating post content (version should increment)...")
    post.content = "This is my first blog post! (Updated)"
    post.save()
    print(f"   After update 1: {post.version}")

    post.title = "My First Post (Revised)"
    post.save()
    print(f"   After update 2: {post.version}")

    post.published = True
    post.save()
    print(f"   After update 3 (published): {post.version}")

    # Reload and verify
    reloaded = BlogPost.get(id="post-1")
    print(f"\n3. Reloaded from database - version: {reloaded.version}")


def example_5_upsert_no_callbacks():
    """Example 5: Upsert bypasses callbacks."""
    print("\n" + "=" * 60)
    print("Example 5: Upsert Bypasses Callbacks")
    print("=" * 60)

    AuditLog.clear()
    EmailService.clear()

    print("\n1. Using upsert() - callbacks should NOT be called...")
    user = User.upsert(id="user-6", email="frank@example.com", name="Frank")

    print(f"   created_at: {user.created_at}")  # Should be None
    print(f"   updated_at: {user.updated_at}")  # Should be None
    print(f"   Audit log entries: {len(AuditLog.entries)}")  # Should be 0
    print(f"   Emails sent: {len(EmailService.sent_emails)}")  # Should be 0

    print("\n2. Using save() - callbacks SHOULD be called...")
    user2 = User(id="user-7", email="grace@example.com", name="Grace")
    user2.save()

    print(f"   created_at: {user2.created_at}")  # Should be set
    print(f"   updated_at: {user2.updated_at}")  # Should be set
    print(f"   Audit log entries: {len(AuditLog.entries)}")  # Should be 1
    print(f"   Emails sent: {len(EmailService.sent_emails)}")  # Should be 1


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# RestMachine ORM - Callbacks Examples")
    print("#" * 60)

    try:
        example_1_automatic_timestamps()
        example_2_audit_logging()
        example_3_notifications()
        example_4_version_tracking()
        example_5_upsert_no_callbacks()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    finally:
        # Cleanup
        backend.clear()
        AuditLog.clear()
        EmailService.clear()


if __name__ == "__main__":
    main()
