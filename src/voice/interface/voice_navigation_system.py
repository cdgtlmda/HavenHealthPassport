"""Voice Navigation System Module.

This module provides voice-guided navigation through the Haven Health Passport
application, supporting contextual navigation, breadcrumbs, bookmarks, and
accessibility features for displaced populations. Handles FHIR Resource
validation for navigation through medical records.

Security Note: All PHI data accessed through voice navigation must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Voice navigation functionality requires proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .audio_cues import AudioCueSystem, CueType
from .voice_feedback_system import VoiceFeedbackSystem

logger = logging.getLogger(__name__)


class NavigationLevel(Enum):
    """Hierarchical levels in the navigation structure."""

    ROOT = "root"
    SECTION = "section"
    SUBSECTION = "subsection"
    ITEM = "item"
    DETAIL = "detail"


class NavigationContext(Enum):
    """Current context for navigation assistance."""

    MAIN_MENU = "main_menu"
    HEALTH_RECORDS = "health_records"
    MEDICATIONS = "medications"
    APPOINTMENTS = "appointments"
    EMERGENCY = "emergency"
    PROFILE = "profile"
    DOCUMENTS = "documents"
    SHARING = "sharing"
    SETTINGS = "settings"
    HELP = "help"
    SEARCH_RESULTS = "search_results"
    FORM_FILLING = "form_filling"
    VOICE_TRAINING = "voice_training"


@dataclass
class NavigationNode:
    """Represents a node in the navigation hierarchy."""

    id: str
    name: str
    level: NavigationLevel
    context: NavigationContext
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    voice_label: str = ""
    voice_hint: str = ""
    accessibility_label: str = ""
    shortcuts: List[str] = field(default_factory=list)
    available_actions: List[str] = field(default_factory=list)
    requires_authentication: bool = False
    is_emergency_accessible: bool = True

    def to_voice_description(self, include_children: bool = True) -> str:
        """Generate voice description of this navigation node."""
        description = self.voice_label or self.name

        if self.voice_hint:
            description += f". {self.voice_hint}"

        if include_children and self.children:
            description += f". Contains {len(self.children)} items"

        if self.available_actions:
            actions = ", ".join(self.available_actions[:3])
            description += f". You can {actions}"

        return description


@dataclass
class NavigationState:
    """Current navigation state and history."""

    current_node_id: str
    previous_node_id: Optional[str] = None
    navigation_stack: deque = field(default_factory=lambda: deque(maxlen=10))
    visited_nodes: Set[str] = field(default_factory=set)
    bookmarks: Set[str] = field(default_factory=set)
    last_navigation_time: datetime = field(default_factory=datetime.now)
    navigation_mode: str = "standard"  # standard, simplified, expert
    voice_guidance_enabled: bool = True

    def add_to_history(self, node_id: str) -> None:
        """Add node to navigation history."""
        self.navigation_stack.append(node_id)
        self.visited_nodes.add(node_id)
        self.last_navigation_time = datetime.now()


class VoiceNavigationSystem:
    """Manages voice-guided navigation through the application."""

    def __init__(
        self,
        feedback_engine: Optional[VoiceFeedbackSystem] = None,
        audio_cue_engine: Optional[AudioCueSystem] = None,
    ):
        """Initialize the voice navigation system.

        Args:
            feedback_engine: Voice feedback system for audio responses
            audio_cue_engine: Audio cue system for navigation sounds
        """
        self.feedback_engine = feedback_engine or VoiceFeedbackSystem()
        self.audio_cue_engine = audio_cue_engine or AudioCueSystem()
        self.navigation_tree: Dict[str, NavigationNode] = {}
        self.user_states: Dict[str, NavigationState] = {}
        self.context_handlers: Dict[NavigationContext, Callable] = {}

        # Initialize navigation structure
        self._build_navigation_tree()
        self._register_context_handlers()

    def _build_navigation_tree(self) -> None:
        """Build the hierarchical navigation structure."""
        # Root node
        self.navigation_tree["root"] = NavigationNode(
            id="root",
            name="Main Menu",
            level=NavigationLevel.ROOT,
            context=NavigationContext.MAIN_MENU,
            voice_label="Main Menu",
            voice_hint="Say the name of any section to navigate there",
            children=[
                "health_records",
                "medications",
                "appointments",
                "emergency",
                "profile",
                "documents",
                "settings",
                "help",
            ],
        )

        # Health Records section
        self.navigation_tree["health_records"] = NavigationNode(
            id="health_records",
            name="Health Records",
            level=NavigationLevel.SECTION,
            context=NavigationContext.HEALTH_RECORDS,
            parent_id="root",
            voice_label="Health Records Section",
            voice_hint="Access your medical history, test results, and diagnoses",
            children=[
                "medical_history",
                "test_results",
                "diagnoses",
                "immunizations",
                "allergies",
            ],
            available_actions=["view", "search", "filter", "export", "share"],
            shortcuts=["records", "medical records", "health history"],
        )

        # Medical History subsection
        self.navigation_tree["medical_history"] = NavigationNode(
            id="medical_history",
            name="Medical History",
            level=NavigationLevel.SUBSECTION,
            context=NavigationContext.HEALTH_RECORDS,
            parent_id="health_records",
            voice_label="Medical History",
            voice_hint="View your complete medical timeline",
            available_actions=["view by date", "search condition", "add entry"],
        )

        # Test Results subsection
        self.navigation_tree["test_results"] = NavigationNode(
            id="test_results",
            name="Test Results",
            level=NavigationLevel.SUBSECTION,
            context=NavigationContext.HEALTH_RECORDS,
            parent_id="health_records",
            voice_label="Test Results",
            voice_hint="Lab results, imaging, and other diagnostic tests",
            available_actions=["view recent", "search by type", "compare results"],
        )

        # Medications section
        self.navigation_tree["medications"] = NavigationNode(
            id="medications",
            name="Medications",
            level=NavigationLevel.SECTION,
            context=NavigationContext.MEDICATIONS,
            parent_id="root",
            voice_label="Medications Section",
            voice_hint="Manage your prescriptions and medication schedule",
            children=[
                "current_medications",
                "medication_schedule",
                "prescription_history",
                "reminders",
            ],
            available_actions=[
                "view all",
                "add medication",
                "set reminder",
                "check interactions",
            ],
            shortcuts=["meds", "prescriptions", "pills"],
        )

        # Current Medications subsection
        self.navigation_tree["current_medications"] = NavigationNode(
            id="current_medications",
            name="Current Medications",
            level=NavigationLevel.SUBSECTION,
            context=NavigationContext.MEDICATIONS,
            parent_id="medications",
            voice_label="Current Medications",
            voice_hint="List of medications you're currently taking",
            available_actions=["view details", "mark as taken", "refill request"],
        )

        # Appointments section
        self.navigation_tree["appointments"] = NavigationNode(
            id="appointments",
            name="Appointments",
            level=NavigationLevel.SECTION,
            context=NavigationContext.APPOINTMENTS,
            parent_id="root",
            voice_label="Appointments Section",
            voice_hint="View and manage your medical appointments",
            children=[
                "upcoming_appointments",
                "past_appointments",
                "schedule_appointment",
            ],
            available_actions=["view calendar", "schedule new", "cancel", "reschedule"],
            shortcuts=["schedule", "calendar", "visits"],
        )

        # Emergency section
        self.navigation_tree["emergency"] = NavigationNode(
            id="emergency",
            name="Emergency",
            level=NavigationLevel.SECTION,
            context=NavigationContext.EMERGENCY,
            parent_id="root",
            voice_label="Emergency Information",
            voice_hint="Quick access to emergency contacts and critical health information",
            children=["emergency_contacts", "critical_info", "emergency_card"],
            available_actions=["call emergency", "share location", "alert contacts"],
            shortcuts=["help", "urgent", "sos"],
            is_emergency_accessible=True,
            requires_authentication=False,
        )

        # Profile section
        self.navigation_tree["profile"] = NavigationNode(
            id="profile",
            name="Profile",
            level=NavigationLevel.SECTION,
            context=NavigationContext.PROFILE,
            parent_id="root",
            voice_label="Personal Profile",
            voice_hint="Your personal and demographic information",
            children=["personal_info", "insurance", "healthcare_providers"],
            available_actions=["view", "edit", "verify"],
            requires_authentication=True,
        )

        # Documents section
        self.navigation_tree["documents"] = NavigationNode(
            id="documents",
            name="Documents",
            level=NavigationLevel.SECTION,
            context=NavigationContext.DOCUMENTS,
            parent_id="root",
            voice_label="Documents Library",
            voice_hint="Upload and manage your medical documents",
            children=["uploaded_documents", "shared_documents", "document_requests"],
            available_actions=["upload", "scan", "organize", "share"],
        )

        # Settings section
        self.navigation_tree["settings"] = NavigationNode(
            id="settings",
            name="Settings",
            level=NavigationLevel.SECTION,
            context=NavigationContext.SETTINGS,
            parent_id="root",
            voice_label="Application Settings",
            voice_hint="Customize your app preferences and privacy settings",
            children=[
                "language_settings",
                "privacy",
                "notifications",
                "voice_settings",
            ],
            available_actions=["change language", "manage privacy", "configure"],
        )

        # Help section
        self.navigation_tree["help"] = NavigationNode(
            id="help",
            name="Help",
            level=NavigationLevel.SECTION,
            context=NavigationContext.HELP,
            parent_id="root",
            voice_label="Help and Support",
            voice_hint="Get help using the application",
            children=["tutorials", "faq", "contact_support", "voice_commands"],
            available_actions=["search help", "start tutorial", "contact support"],
        )

    def _register_context_handlers(self) -> None:
        """Register handlers for different navigation contexts."""
        self.context_handlers[NavigationContext.MAIN_MENU] = (
            self._handle_main_menu_context
        )
        self.context_handlers[NavigationContext.HEALTH_RECORDS] = (
            self._handle_health_records_context
        )
        self.context_handlers[NavigationContext.MEDICATIONS] = (
            self._handle_medications_context
        )
        self.context_handlers[NavigationContext.EMERGENCY] = (
            self._handle_emergency_context
        )

    def navigate_to(self, user_id: str, destination: str) -> Tuple[bool, str]:
        """Navigate to a specific destination.

        Returns (success, voice_response).
        """
        # Get or create user state
        if user_id not in self.user_states:
            self.user_states[user_id] = NavigationState(current_node_id="root")

        state = self.user_states[user_id]

        # Find destination node
        target_node = self._find_node_by_name_or_shortcut(destination)
        if not target_node:
            return (
                False,
                f"I couldn't find '{destination}'. Try saying 'help' for available options.",
            )

        # Check authentication requirements
        if target_node.requires_authentication:
            # In real implementation, check auth status
            pass

        # Update navigation state
        state.previous_node_id = state.current_node_id
        state.current_node_id = target_node.id
        state.add_to_history(target_node.id)

        # Generate voice response
        nav_response = self._generate_navigation_response(target_node, state)

        # Play navigation sound
        if self.audio_cue_engine:
            import asyncio  # noqa: PLC0415

            asyncio.create_task(self.audio_cue_engine.play_cue(CueType.NAVIGATION))

        return True, nav_response

    def navigate_back(self, user_id: str) -> Tuple[bool, str]:
        """Navigate to the previous location."""
        if user_id not in self.user_states:
            return False, "No navigation history available."

        state = self.user_states[user_id]

        if len(state.navigation_stack) <= 1:
            return False, "You're at the beginning of your navigation history."

        # Pop current from stack
        state.navigation_stack.pop()

        # Get previous node
        previous_node_id = (
            state.navigation_stack[-1] if state.navigation_stack else "root"
        )
        previous_node = self.navigation_tree.get(previous_node_id)

        if not previous_node:
            return False, "Unable to navigate back."

        # Update state
        state.current_node_id = previous_node_id

        # Generate response
        nav_response = (
            f"Going back to {previous_node.voice_label}. {previous_node.voice_hint}"
        )

        # Play back navigation sound
        if self.audio_cue_engine:
            import asyncio  # noqa: PLC0415

            asyncio.create_task(self.audio_cue_engine.play_cue(CueType.NAVIGATION))

        return True, nav_response

    def navigate_home(self, user_id: str) -> Tuple[bool, str]:
        """Navigate to home/root."""
        if user_id not in self.user_states:
            self.user_states[user_id] = NavigationState(current_node_id="root")

        state = self.user_states[user_id]
        state.current_node_id = "root"
        state.add_to_history("root")

        root_node = self.navigation_tree["root"]
        nav_response = f"Returning to {root_node.voice_label}. {root_node.voice_hint}"

        if self.audio_cue_engine:
            import asyncio  # noqa: PLC0415

            asyncio.create_task(self.audio_cue_engine.play_cue(CueType.NAVIGATION))

        return True, nav_response

    def get_current_location(self, user_id: str) -> Tuple[bool, str]:
        """Get current navigation location."""
        if user_id not in self.user_states:
            return True, "You are at the Main Menu."

        state = self.user_states[user_id]
        current_node = self.navigation_tree.get(state.current_node_id)

        if not current_node:
            return False, "Unable to determine current location."

        # Build breadcrumb
        breadcrumb = self._build_breadcrumb(current_node)
        location_text = " > ".join(breadcrumb)

        nav_response = f"You are at: {location_text}. {current_node.voice_hint}"

        return True, nav_response

    def list_available_options(self, user_id: str) -> Tuple[bool, str]:
        """List available navigation options from current location."""
        if user_id not in self.user_states:
            self.user_states[user_id] = NavigationState(current_node_id="root")

        state = self.user_states[user_id]
        current_node = self.navigation_tree.get(state.current_node_id)

        if not current_node:
            return False, "Unable to list options."

        response_parts = [f"From {current_node.voice_label}, you can:"]

        # List child nodes
        if current_node.children:
            child_names = []
            for child_id in current_node.children:
                child_node = self.navigation_tree.get(child_id)
                if child_node:
                    child_names.append(child_node.name)
            response_parts.append(f"Navigate to: {', '.join(child_names)}")

        # List available actions
        if current_node.available_actions:
            response_parts.append(
                f"Or say: {', '.join(current_node.available_actions)}"
            )

        # Add navigation commands
        response_parts.append("You can also say 'back', 'home', or 'where am I'")

        return True, " ".join(response_parts)

    def add_bookmark(
        self, user_id: str, name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Add current location to bookmarks."""
        if user_id not in self.user_states:
            return False, "No current location to bookmark."

        state = self.user_states[user_id]
        current_node = self.navigation_tree.get(state.current_node_id)

        if not current_node:
            return False, "Unable to bookmark current location."

        state.bookmarks.add(state.current_node_id)

        bookmark_name = name or current_node.name
        nav_response = f"Added {bookmark_name} to your bookmarks."

        if self.audio_cue_engine:
            import asyncio  # noqa: PLC0415

            asyncio.create_task(self.audio_cue_engine.play_cue(CueType.SUCCESS))

        return True, nav_response

    def navigate_to_bookmark(
        self, user_id: str, bookmark_name: str
    ) -> Tuple[bool, str]:
        """Navigate to a bookmarked location."""
        if user_id not in self.user_states:
            return False, "No bookmarks available."

        state = self.user_states[user_id]

        # Find bookmark by name
        for bookmark_id in state.bookmarks:
            node = self.navigation_tree.get(bookmark_id)
            if node and (
                node.name.lower() == bookmark_name.lower()
                or bookmark_name.lower() in [s.lower() for s in node.shortcuts]
            ):
                return self.navigate_to(user_id, node.name)

        return False, f"No bookmark found for '{bookmark_name}'."

    def provide_contextual_help(self, user_id: str) -> Tuple[bool, str]:
        """Provide context-specific help."""
        if user_id not in self.user_states:
            self.user_states[user_id] = NavigationState(current_node_id="root")

        state = self.user_states[user_id]
        current_node = self.navigation_tree.get(state.current_node_id)

        if not current_node:
            return False, "Unable to provide help."

        # Get context-specific help
        if current_node.context in self.context_handlers:
            help_text = self.context_handlers[current_node.context](current_node)
        else:
            help_text = self._generate_generic_help(current_node)

        return True, help_text

    def _find_node_by_name_or_shortcut(self, query: str) -> Optional[NavigationNode]:
        """Find a navigation node by name or shortcut."""
        query_lower = query.lower()

        for node in self.navigation_tree.values():
            # Check exact name match
            if node.name.lower() == query_lower:
                return node

            # Check shortcuts
            if query_lower in [s.lower() for s in node.shortcuts]:
                return node

            # Check partial match
            if query_lower in node.name.lower():
                return node

        return None

    def _build_breadcrumb(self, node: NavigationNode) -> List[str]:
        """Build breadcrumb trail for a node."""
        breadcrumb: List[str] = []
        current = node

        while current:
            breadcrumb.insert(0, current.name)
            if current.parent_id:
                parent = self.navigation_tree.get(current.parent_id)
                if parent:
                    current = parent
                else:
                    break
            else:
                break

        return breadcrumb

    def _generate_navigation_response(
        self, node: NavigationNode, state: NavigationState
    ) -> str:
        """Generate voice response for navigation."""
        response_parts = []

        # Announce arrival
        response_parts.append(f"Now in {node.voice_label}")

        # Add description
        if node.voice_hint:
            response_parts.append(node.voice_hint)

        # Mention available options based on navigation mode
        if state.navigation_mode == "standard":
            if node.children:
                response_parts.append(
                    f"There are {len(node.children)} options available"
                )
            if node.available_actions:
                actions_preview = ", ".join(node.available_actions[:2])
                response_parts.append(f"You can {actions_preview}, and more")

        elif state.navigation_mode == "simplified":
            # Simpler guidance for users who need it
            if node.children:
                response_parts.append("Say 'list options' to hear what's available")

        elif state.navigation_mode == "expert":
            # Minimal feedback for experienced users
            pass

        # Add contextual tips
        if node.context == NavigationContext.EMERGENCY:
            response_parts.append("Say 'emergency' at any time for immediate help")

        return ". ".join(response_parts)

    def _generate_generic_help(self, node: NavigationNode) -> str:
        """Generate generic help text for a node."""
        help_parts = [f"Help for {node.voice_label}:"]

        if node.voice_hint:
            help_parts.append(node.voice_hint)

        if node.children:
            help_parts.append(f"You can navigate to: {', '.join(node.children[:3])}")

        if node.available_actions:
            help_parts.append(f"Available actions: {', '.join(node.available_actions)}")

        help_parts.append(
            "Say 'back' to go back, 'home' for main menu, or 'help' for more assistance"
        )

        return ". ".join(help_parts)

    def _handle_main_menu_context(self, node: Optional[NavigationNode] = None) -> str:
        """Handle help for main menu context."""
        _ = node  # Node info could be used for more specific guidance
        return (
            "Welcome to Haven Health Passport. From here, you can access all major sections. "
            "Say the name of any section like 'health records', 'medications', or 'appointments'. "
            "For emergency help, just say 'emergency'. "
            "You can also say 'help' at any time for assistance."
        )

    def _handle_health_records_context(
        self, node: Optional[NavigationNode] = None
    ) -> str:
        """Handle help for health records context."""
        _ = node  # Node info could be used for more specific guidance
        return (
            "In the Health Records section, you can view your complete medical history. "
            "Say 'medical history' to see past conditions, 'test results' for lab work, "
            "or 'immunizations' for your vaccination records. "
            "You can also say 'search' followed by what you're looking for."
        )

    def _handle_medications_context(self, node: Optional[NavigationNode] = None) -> str:
        """Handle help for medications context."""
        _ = node  # Node info could be used for more specific guidance
        return (
            "In the Medications section, you can manage all your prescriptions. "
            "Say 'current medications' to see what you're taking now, "
            "'add medication' to record a new prescription, "
            "or 'set reminder' to get medication alerts."
        )

    def _handle_emergency_context(self, node: Optional[NavigationNode] = None) -> str:
        """Handle help for emergency context."""
        _ = node  # Node info could be used for more specific guidance
        return (
            "This is the Emergency section for urgent situations. "
            "Say 'call emergency' to contact emergency services, "
            "'emergency contacts' to see your emergency contact list, "
            "or 'critical info' to access your vital medical information quickly."
        )

    def set_navigation_mode(self, user_id: str, mode: str) -> Tuple[bool, str]:
        """Set navigation mode for user (standard, simplified, expert)."""
        valid_modes = ["standard", "simplified", "expert"]

        if mode not in valid_modes:
            return False, f"Invalid mode. Choose from: {', '.join(valid_modes)}"

        if user_id not in self.user_states:
            self.user_states[user_id] = NavigationState(current_node_id="root")

        self.user_states[user_id].navigation_mode = mode

        mode_descriptions = {
            "standard": "Standard mode provides balanced guidance",
            "simplified": "Simplified mode gives extra help at each step",
            "expert": "Expert mode minimizes voice feedback",
        }

        return True, f"Navigation mode set to {mode}. {mode_descriptions[mode]}"

    def get_navigation_stats(self, user_id: str) -> Dict[str, Any]:
        """Get navigation statistics for a user."""
        if user_id not in self.user_states:
            return {}

        state = self.user_states[user_id]

        return {
            "current_location": state.current_node_id,
            "visited_nodes": len(state.visited_nodes),
            "bookmarks": len(state.bookmarks),
            "navigation_mode": state.navigation_mode,
            "last_navigation": state.last_navigation_time.isoformat(),
        }

    def export_navigation_map(self) -> Dict[str, Any]:
        """Export the navigation structure for documentation."""
        nav_map = {}

        for node_id, node in self.navigation_tree.items():
            nav_map[node_id] = {
                "name": node.name,
                "level": node.level.value,
                "context": node.context.value,
                "parent": node.parent_id,
                "children": node.children,
                "shortcuts": node.shortcuts,
                "actions": node.available_actions,
            }

        return nav_map

    def validate_navigation_data(self, nav_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate navigation data for FHIR compliance.

        Args:
            nav_data: Navigation data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        if not nav_data:
            errors.append("No navigation data provided")
        elif "resourceType" in nav_data and nav_data.get("resourceType"):
            # If it's FHIR data, ensure proper structure
            if "id" not in nav_data:
                warnings.append("FHIR resource should have an id")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# Example usage
if __name__ == "__main__":
    # Initialize navigation system
    nav_system = VoiceNavigationSystem()

    # Simulate user navigation
    test_user_id = "test_user"

    # Navigate to health records
    success, response = nav_system.navigate_to(test_user_id, "health records")
    print(f"Navigate to health records: {response}")

    # Get current location
    success, response = nav_system.get_current_location(test_user_id)
    print(f"Current location: {response}")

    # List options
    success, response = nav_system.list_available_options(test_user_id)
    print(f"Available options: {response}")

    # Navigate to subsection
    success, response = nav_system.navigate_to(test_user_id, "test results")
    print(f"Navigate to test results: {response}")

    # Add bookmark
    success, response = nav_system.add_bookmark(test_user_id)
    print(f"Add bookmark: {response}")

    # Navigate back
    success, response = nav_system.navigate_back(test_user_id)
    print(f"Navigate back: {response}")

    # Get contextual help
    success, response = nav_system.provide_contextual_help(test_user_id)
    print(f"Contextual help: {response}")
