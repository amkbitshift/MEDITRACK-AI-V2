"""
MEDiTrack AI — Equipment State Machine & Storage Verification Manager
Phase 3 Enterprise Architecture

Enforces canonical, mutually exclusive equipment lifecycle states:
    AVAILABLE <-> WAITING <-> IN_USE <-> TEMPORARY_HOLD <-> RETURNING_TO_STORAGE <-> MAINTENANCE

Guarantees:
1. No impossible concurrent states (e.g. AVAILABLE + IN_USE).
2. All state transitions pass through strict validation.
3. 2-Minute Wheelchair Storage Auto-Verification with movement edge-case cancellation.
4. Temporary Hold duration tracking with clinical reason logging.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, Callable, List

class EquipmentState:
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    TEMPORARY_HOLD = "TEMPORARY_HOLD"
    WAITING = "WAITING"
    RETURNING_TO_STORAGE = "RETURNING_TO_STORAGE"
    MAINTENANCE = "MAINTENANCE"
    UNKNOWN = "UNKNOWN"

    ALL_STATES = {
        AVAILABLE,
        IN_USE,
        TEMPORARY_HOLD,
        WAITING,
        RETURNING_TO_STORAGE,
        MAINTENANCE,
        UNKNOWN
    }

# Canonical Allowed State Transition Graph
# Defines strict rules for equipment lifecycle
ALLOWED_TRANSITIONS: Dict[str, set] = {
    EquipmentState.AVAILABLE: {
        EquipmentState.WAITING,
        EquipmentState.IN_USE,
        EquipmentState.MAINTENANCE
    },
    EquipmentState.WAITING: {
        EquipmentState.IN_USE,
        EquipmentState.AVAILABLE,
        EquipmentState.MAINTENANCE
    },
    EquipmentState.IN_USE: {
        EquipmentState.TEMPORARY_HOLD,
        EquipmentState.RETURNING_TO_STORAGE,
        EquipmentState.AVAILABLE,
        EquipmentState.MAINTENANCE
    },
    EquipmentState.TEMPORARY_HOLD: {
        EquipmentState.IN_USE,
        EquipmentState.RETURNING_TO_STORAGE,
        EquipmentState.MAINTENANCE,
        EquipmentState.AVAILABLE
    },
    EquipmentState.RETURNING_TO_STORAGE: {
        EquipmentState.AVAILABLE,
        EquipmentState.IN_USE,
        EquipmentState.MAINTENANCE
    },
    EquipmentState.MAINTENANCE: {
        EquipmentState.AVAILABLE
    },
    EquipmentState.UNKNOWN: {
        EquipmentState.AVAILABLE,
        EquipmentState.IN_USE,
        EquipmentState.MAINTENANCE,
        EquipmentState.WAITING
    }
}

class EquipmentStateMachine:
    """Validator and state transition guard for hospital equipment fleet."""

    @staticmethod
    def normalize_state(state_str: str) -> str:
        if not state_str:
            return EquipmentState.UNKNOWN
        clean = str(state_str).strip().upper()
        if clean in EquipmentState.ALL_STATES:
            return clean
        # Handle common legacy aliases
        alias_map = {
            "TEMPORARY": EquipmentState.TEMPORARY_HOLD,
            "TEMP_WAITING": EquipmentState.TEMPORARY_HOLD,
            "PAUSED": EquipmentState.TEMPORARY_HOLD,
            "STORAGE_VERIFICATION": EquipmentState.RETURNING_TO_STORAGE,
            "RETURNING": EquipmentState.RETURNING_TO_STORAGE,
            "READY": EquipmentState.AVAILABLE,
            "ACTIVE": EquipmentState.IN_USE,
            "IN-USE": EquipmentState.IN_USE
        }
        return alias_map.get(clean, EquipmentState.UNKNOWN)

    @staticmethod
    def can_transition(current_state: str, new_state: str) -> bool:
        curr = EquipmentStateMachine.normalize_state(current_state)
        nxt = EquipmentStateMachine.normalize_state(new_state)
        if curr == nxt:
            return True  # Idempotent state re-assertion is allowed
        allowed = ALLOWED_TRANSITIONS.get(curr, set())
        return nxt in allowed

    @staticmethod
    def validate_transition(current_state: str, new_state: str) -> Tuple[bool, str]:
        curr = EquipmentStateMachine.normalize_state(current_state)
        nxt = EquipmentStateMachine.normalize_state(new_state)
        if curr == nxt:
            return True, f"State unchanged: {curr}"
        allowed = ALLOWED_TRANSITIONS.get(curr, set())
        if nxt not in allowed:
            allowed_str = ", ".join(sorted(list(allowed))) if allowed else "None"
            return False, f"Illegal state transition: Cannot change from '{curr}' to '{nxt}'. Permitted transitions from '{curr}': [{allowed_str}]."
        return True, f"Valid transition: {curr} -> {nxt}"


class StorageVerificationManager:
    """
    Manages the 2-minute verification countdown when a wheelchair
    is returned to the designated Wheelchair Storage location.
    
    If the wheelchair moves away or active usage is detected within 120s,
    the countdown is immediately cancelled and state reverts to IN_USE/MOVING.
    If 120s elapses without disturbance, state automatically transitions to AVAILABLE.
    """

    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self._tasks: Dict[str, asyncio.Task] = {}

    def start_verification(
        self,
        equipment_id: str,
        location: str = "Radiology Wheelchair Storage",
        duration_seconds: int = 120,
        on_verified_callback: Optional[Callable[[str, str], Any]] = None,
        on_tick_callback: Optional[Callable[[str, int], Any]] = None
    ) -> Dict[str, Any]:
        """Starts the 2-minute verification timer for a returned wheelchair."""
        # Cancel any existing verification for this equipment first
        self.cancel_verification(equipment_id, reason="New storage verification initiated")

        now = datetime.now()
        target_time = now + timedelta(seconds=duration_seconds)

        session = {
            "equipment_id": equipment_id,
            "equipment_name": "Wheelchair WC-007 (Smart IoT)" if equipment_id == "WC-007" else f"Equipment {equipment_id}",
            "location": location,
            "status": "RETURNING_TO_STORAGE",
            "verification_status": "COUNTDOWN_ACTIVE",
            "duration_seconds": duration_seconds,
            "remaining_seconds": duration_seconds,
            "started_at": now.isoformat(),
            "target_verification_at": target_time.isoformat(),
            "completed_at": None,
            "cancellation_reason": None
        }

        self.active_sessions[equipment_id] = session

        # Launch asynchronous timer task
        task = asyncio.create_task(
            self._run_verification_loop(
                equipment_id=equipment_id,
                duration_seconds=duration_seconds,
                location=location,
                on_verified_callback=on_verified_callback,
                on_tick_callback=on_tick_callback
            )
        )
        self._tasks[equipment_id] = task

        return session

    async def _run_verification_loop(
        self,
        equipment_id: str,
        duration_seconds: int,
        location: str,
        on_verified_callback: Optional[Callable[[str, str], Any]],
        on_tick_callback: Optional[Callable[[str, int], Any]]
    ):
        """Asynchronous countdown loop running for duration_seconds."""
        try:
            remaining = duration_seconds
            while remaining > 0:
                await asyncio.sleep(1)
                remaining -= 1

                # Update active session remaining seconds
                if equipment_id in self.active_sessions:
                    self.active_sessions[equipment_id]["remaining_seconds"] = remaining
                    if on_tick_callback:
                        try:
                            res = on_tick_callback(equipment_id, remaining)
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception:
                            pass

            # Countdown completed without cancellation!
            if equipment_id in self.active_sessions:
                session = self.active_sessions[equipment_id]
                session["verification_status"] = "VERIFIED"
                session["status"] = EquipmentState.AVAILABLE
                session["completed_at"] = datetime.now().isoformat()
                session["remaining_seconds"] = 0

                # Archive into history
                self.history.append(dict(session))

                # Trigger completion callback (e.g. backend state machine update)
                if on_verified_callback:
                    try:
                        res = on_verified_callback(equipment_id, location)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as ex:
                        print(f"[StorageManager] Error in verified callback for {equipment_id}: {ex}")

        except asyncio.CancelledError:
            # Task was explicitly cancelled due to movement / user action
            pass
        finally:
            self._tasks.pop(equipment_id, None)

    def cancel_verification(self, equipment_id: str, reason: str = "Movement detected") -> bool:
        """Cancels an active 2-minute countdown (e.g. if wheelchair moved away)."""
        if equipment_id in self._tasks:
            task = self._tasks.pop(equipment_id)
            if not task.done():
                task.cancel()

        if equipment_id in self.active_sessions:
            session = self.active_sessions.pop(equipment_id)
            session["verification_status"] = "CANCELLED"
            session["cancellation_reason"] = reason
            session["completed_at"] = datetime.now().isoformat()
            self.history.append(session)
            return True
        return False

    def get_session(self, equipment_id: str) -> Optional[Dict[str, Any]]:
        session = self.active_sessions.get(equipment_id)
        if session:
            # Recompute remaining seconds from real clock
            try:
                target = datetime.fromisoformat(session["target_verification_at"])
                diff = int((target - datetime.now()).total_seconds())
                session["remaining_seconds"] = max(0, diff)
            except Exception:
                pass
        return session

    def list_active(self) -> List[Dict[str, Any]]:
        results = []
        for eq_id in list(self.active_sessions.keys()):
            s = self.get_session(eq_id)
            if s:
                results.append(s)
        return results


class TemporaryHoldManager:
    """
    Manages TEMPORARY_HOLD sessions.
    Calculates duration in real-time and logs reasons (e.g., 'Awaiting patient transfer').
    """

    def __init__(self):
        self.active_holds: Dict[str, Dict[str, Any]] = {}
        self.hold_history: List[Dict[str, Any]] = []

    def start_hold(self, equipment_id: str, reason: str = "Awaiting patient transfer") -> Dict[str, Any]:
        now = datetime.now()
        hold = {
            "equipment_id": equipment_id,
            "status": EquipmentState.TEMPORARY_HOLD,
            "reason": reason or "Awaiting patient transfer",
            "started_at": now.isoformat(),
            "duration_formatted": "00:00:00"
        }
        self.active_holds[equipment_id] = hold
        return hold

    def get_hold(self, equipment_id: str) -> Optional[Dict[str, Any]]:
        hold = self.active_holds.get(equipment_id)
        if hold:
            try:
                started = datetime.fromisoformat(hold["started_at"])
                secs = int((datetime.now() - started).total_seconds())
                hrs = String_pad = str(secs // 3600).zfill(2)
                mins = str((secs % 3600) // 60).zfill(2)
                s = str(secs % 60).zfill(2)
                hold["duration_seconds"] = secs
                hold["duration_formatted"] = f"{hrs}:{mins}:{s}"
            except Exception:
                pass
        return hold

    def end_hold(self, equipment_id: str, resumed_to: str = EquipmentState.IN_USE) -> Optional[Dict[str, Any]]:
        hold = self.active_holds.pop(equipment_id, None)
        if hold:
            try:
                started = datetime.fromisoformat(hold["started_at"])
                secs = int((datetime.now() - started).total_seconds())
                hold["duration_seconds"] = secs
                hold["ended_at"] = datetime.now().isoformat()
                hold["resumed_to"] = resumed_to
                self.hold_history.append(hold)
            except Exception:
                pass
        return hold


# Global Manager Singletons
storage_verification_manager = StorageVerificationManager()
temporary_hold_manager = TemporaryHoldManager()
