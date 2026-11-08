# Timing Boundary Definition

APP_VISIBLE_TIMING_VALIDATED=yes
IN_RUNTIME_TIMING_AVAILABLE=no
PERFORMANCE_SCOPE=APP_VISIBLE_OPEN_LATENCY_ONLY
TIMER_API=android.os.SystemClock.elapsedRealtimeNanos
TIMER_PLATFORM_IMPLEMENTATION=Android framework monotonic elapsed realtime nanos on guest

P0/P1 start: immediately before ContentResolver.openFileDescriptor(non-target-uri, "rw").
P0/P1 end: immediately after the call returns a non-null PFD.
P2 start: immediately before ContentResolver.openFileDescriptor(target-uri, "rw").
P2 end: immediately after the expected denial exception/result returns with no PFD.

PFD usability verification and minimum payload write/close are performed after the timed region.
No debugfs/counter/log/file export operation is inside the timed region.
