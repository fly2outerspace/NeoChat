"""Virtual time provider for session-based time management"""
import threading
from datetime import datetime, timedelta
import json
from typing import Literal, Optional, List
from dataclasses import dataclass, field


@dataclass
class TimeAction:
    """Single transformation applied to session virtual time."""
    type: Literal["scale", "offset", "freeze"] = "scale"
    value: float = 1.0
    note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "value": self.value,
            "note": self.note,
        }

    @staticmethod
    def from_dict(data: dict) -> "TimeAction":
        return TimeAction(
            type=data.get("type", "scale"),
            value=float(data.get("value", 1.0)),
            note=data.get("note"),
        )


@dataclass
class SessionClock:
    """Timeline configuration for a session."""
    session_id: str
    base_virtual: datetime
    base_real: datetime
    actions: List[TimeAction] = field(default_factory=list)
    updated_at: Optional[str] = None
    real_updated_at: Optional[str] = None


class TimeProvider:
    """Singleton time provider managing virtual time for sessions"""
    
    _instance: Optional["TimeProvider"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize time provider"""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    real_now = datetime.now()
                    self._session_clocks: dict[str, SessionClock] = {}
                    self._default_clock = SessionClock(
                        session_id="__default__",
                        base_virtual=real_now,
                        base_real=real_now,
                        actions=[],
                    )
                    self._initialized = True
    
    def _get_real_now(self) -> datetime:
        """Get real system time"""
        return datetime.now()
    
    def _create_default_clock(self, session_id: str) -> SessionClock:
        real_now = self._get_real_now()
        return SessionClock(
            session_id=session_id,
            base_virtual=real_now,
            base_real=real_now,
            actions=[],
        )

    def _get_clock(self, session_id: Optional[str]) -> SessionClock:
        """Get clock for session, or default if None
        
        If session_id is not in memory, attempts to load from database first.
        Only creates a default clock if no database record exists.
        """
        if not session_id:
            return self._default_clock
        if session_id not in self._session_clocks:
            # Try to load from database first
            # Use lazy import to avoid circular import issues
            try:
                from app.storage.session_clock_repository import SessionClockRepository
                from app.logger import logger
                
                clock_repo = SessionClockRepository()
                clock_data = clock_repo.get_by_session_id(session_id)
                if clock_data:
                    # Load from database
                    self._session_clocks[session_id] = self.load_session_clock(
                        session_id=session_id,
                        base_virtual=clock_data.get('virtual_base'),
                        base_real=clock_data.get('real_base'),
                        actions=clock_data.get('actions'),
                    )
                else:
                    # No database record, create default clock
                    self._session_clocks[session_id] = self._create_default_clock(session_id)
            except Exception as e:
                # If loading from database fails, create default clock
                # This ensures the system continues to work even if database is unavailable
                try:
                    from app.logger import logger
                    logger.warning(f"Failed to load session clock from database for {session_id}: {e}, creating default clock")
                except ImportError:
                    # If logger is not available, just create default clock silently
                    pass
                self._session_clocks[session_id] = self._create_default_clock(session_id)
        return self._session_clocks[session_id]
    
    def _compute_virtual_time(self, clock: SessionClock, real_now: Optional[datetime] = None) -> datetime:
        """Compute virtual time for provided clock using optional real_now"""
        real_now = real_now or self._get_real_now()
        virtual = clock.base_virtual
        real_delta = (real_now - clock.base_real).total_seconds()

        for action in clock.actions:
            if action.type == "scale":
                real_delta *= action.value
            elif action.type == "offset":
                virtual += timedelta(seconds=action.value)
            elif action.type == "freeze":
                real_delta = 0.0

        virtual += timedelta(seconds=real_delta)
        return virtual

    def now(self, session_id: Optional[str] = None) -> datetime:
        """Get current virtual time for session
        
        Args:
            session_id: Session ID. If None, uses default clock.
        
        Returns:
            Current virtual datetime
        """
        clock = self._get_clock(session_id)
        return self._compute_virtual_time(clock)
    
    def now_str(
        self,
        format: Literal["readable", "iso", "timestamp", "logfile"] = "readable",
        session_id: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> str:
        """Get current virtual time as string
        
        Args:
            format: Time format
            session_id: Session ID
            timezone: Optional timezone name
        
        Returns:
            Formatted time string
        """
        now = self.now(session_id)
        
        # Handle timezone if provided
        if timezone:
            try:
                import pytz
                tz = pytz.timezone(timezone)
                # Convert naive datetime to timezone-aware
                if now.tzinfo is None:
                    now = tz.localize(now)
                else:
                    now = now.astimezone(tz)
            except ImportError:
                raise ImportError("pytz library is required for timezone support. Install it with: pip install pytz")
            except Exception as e:
                raise ValueError(f"Invalid timezone '{timezone}': {e}")
        
        # Format the time
        if format == "iso":
            return now.isoformat()
        elif format == "timestamp":
            return str(int(now.timestamp()))
        elif format == "logfile":
            return now.strftime("%Y%m%d%H%M%S")
        else:  # readable (default)
            return now.strftime("%Y-%m-%d %H:%M:%S")
    
    def real_now(self) -> datetime:
        """Get real system time (always real, never virtual)"""
        return self._get_real_now()

    def _touch_clock(self, clock: SessionClock, real_now: Optional[datetime] = None):
        """Update metadata timestamps for a clock"""
        real_now = real_now or self._get_real_now()
        virtual_now = self._compute_virtual_time(clock, real_now)
        clock.updated_at = virtual_now.strftime('%Y-%m-%d %H:%M:%S')
        clock.real_updated_at = real_now.strftime('%Y-%m-%d %H:%M:%S')

    def _rebase_clock(self, clock: SessionClock, real_now: Optional[datetime] = None):
        """Flatten current actions into baseline"""
        real_now = real_now or self._get_real_now()
        current_virtual = self._compute_virtual_time(clock, real_now)
        clock.base_virtual = current_virtual
        clock.base_real = real_now
        clock.actions = []
        self._touch_clock(clock, real_now)
    
    def real_now_str(
        self,
        format: Literal["readable", "iso", "timestamp", "logfile"] = "readable",
        timezone: Optional[str] = None
    ) -> str:
        """Get real system time as string (always real, never virtual)"""
        now = self.real_now()
        
        if timezone:
            try:
                import pytz
                tz = pytz.timezone(timezone)
                if now.tzinfo is None:
                    now = tz.localize(now)
                else:
                    now = now.astimezone(tz)
            except ImportError:
                raise ImportError("pytz library is required for timezone support. Install it with: pip install pytz")
            except Exception as e:
                raise ValueError(f"Invalid timezone '{timezone}': {e}")
        
        if format == "iso":
            return now.isoformat()
        elif format == "timestamp":
            return str(int(now.timestamp()))
        elif format == "logfile":
            return now.strftime("%Y%m%d%H%M%S")
        else:  # readable (default)
            return now.strftime("%Y-%m-%d %H:%M:%S")
    
    def _parse_time_string(self, value: str) -> datetime:
        try:
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError as exc:
            raise ValueError(f"Invalid time format '{value}', expected 'YYYY-MM-DD HH:MM:SS'") from exc

    def update_session_clock(
        self,
        session_id: str,
        base_virtual: Optional[datetime | str] = None,
        actions: Optional[List[TimeAction | dict]] = None,
        rebase_current: bool = False,
        base_real: Optional[datetime] = None,
    ) -> SessionClock:
        """Update or create session clock timeline."""
        with self._lock:
            clock = self._get_clock(session_id)
            real_now = base_real or self._get_real_now()

            if rebase_current and base_virtual is None:
                self._rebase_clock(clock, real_now)

            if base_virtual is not None:
                base_virtual_dt = (
                    self._parse_time_string(base_virtual)
                    if isinstance(base_virtual, str)
                    else base_virtual
                )
                clock.base_virtual = base_virtual_dt
                clock.base_real = real_now
                if actions is not None:
                    parsed_actions = [
                        action if isinstance(action, TimeAction) else TimeAction.from_dict(action)
                        for action in actions
                    ]
                    clock.actions = parsed_actions
                else:
                    clock.actions = []
                self._touch_clock(clock, real_now)
                return clock
            else:
                clock.base_real = real_now

            if actions is not None:
                parsed_actions: List[TimeAction] = []
                for action in actions:
                    if isinstance(action, TimeAction):
                        parsed_actions.append(action)
                    else:
                        parsed_actions.append(TimeAction.from_dict(action))
                clock.actions = parsed_actions

            self._touch_clock(clock, real_now)
            return clock
    
    def seek(self, session_id: str, virtual_time: str) -> SessionClock:
        """Seek to a specific virtual time point
        
        Args:
            session_id: Session ID
            virtual_time: Target virtual time (format: 'YYYY-MM-DD HH:MM:SS')
        
        Returns:
            Updated SessionClock
        """
        try:
            target_dt = datetime.strptime(virtual_time, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ValueError(f"Invalid time format: {virtual_time}. Expected 'YYYY-MM-DD HH:MM:SS'")
        
        with self._lock:
            clock = self._get_clock(session_id)
            real_now = self._get_real_now()
            clock.base_virtual = target_dt
            clock.base_real = real_now
            clock.actions = []
            self._touch_clock(clock, real_now)
            return clock
    
    def nudge(self, session_id: str, delta_seconds: float) -> SessionClock:
        """Nudge time forward or backward by delta seconds
        
        Args:
            session_id: Session ID
            delta_seconds: Time delta in seconds (positive = forward, negative = backward)
        
        Returns:
            Updated SessionClock
        """
        return self.append_action(
            session_id,
            TimeAction(type="offset", value=delta_seconds),
        )
    
    def set_speed(self, session_id: str, speed: float) -> SessionClock:
        """Set time speed multiplier
        
        Args:
            session_id: Session ID
            speed: Speed multiplier (1.0 = normal, 2.0 = 2x, 0.0 = paused)
        
        Returns:
            Updated SessionClock
        """
        return self.append_action(
            session_id,
            TimeAction(type="scale", value=speed),
            rebase_before=True,
        )

    def append_action(self, session_id: str, action: TimeAction, rebase_before: bool = False) -> SessionClock:
        with self._lock:
            clock = self._get_clock(session_id)
            if rebase_before:
                self._rebase_clock(clock)
            clock.actions.append(action)
            self._touch_clock(clock)
            return clock

    def clear_actions(self, session_id: str) -> SessionClock:
        with self._lock:
            clock = self._get_clock(session_id)
            clock.actions = []
            self._touch_clock(clock)
            return clock
    
    def get_session_clock(self, session_id: str) -> SessionClock:
        """Get session clock configuration"""
        return self._get_clock(session_id)
    
    def load_session_clock(
        self,
        session_id: str,
        base_virtual: Optional[str],
        base_real: Optional[str],
        actions: Optional[str] = None,
    ) -> SessionClock:
        """Load session clock from database"""
        with self._lock:
            clock = self._create_default_clock(session_id)

            if base_virtual:
                clock.base_virtual = self._parse_time_string(base_virtual)
            if base_real:
                clock.base_real = self._parse_time_string(base_real)

            if actions:
                try:
                    data = json.loads(actions)
                except json.JSONDecodeError:
                    data = []
                clock.actions = [TimeAction.from_dict(item) for item in data]

            self._session_clocks[session_id] = clock
            self._touch_clock(clock)
            return clock


# Global singleton instance
time_provider = TimeProvider()

