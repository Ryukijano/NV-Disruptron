# NV-Disruptron Changelog

## [Unreleased] - 2026-06-13

### Added
- **Autonomous Watcher Loop**: Background task that proactively monitors TfL JamCams
  - Samples cameras every 30 seconds (configurable via `WATCH_INTERVAL_S`)
  - Runs detection via LocateAnything-3B on camera snapshots
  - Emits detection and panel events to all connected frontend clients
  - Checks TfL for severe disruptions and emits alerts
  - New files: `disruptron_api/backend/watcher.py`, `disruptron_api/backend/camera_watch.py`

- **Real TfL Congestion Data Integration**: 
  - New endpoint: `GET /v1/geo/road-congestion`
  - Fetches live road status from TfL Unified API (`/Road/all/Status`)
  - Parses TfL bounds/envelope coordinates to create LineString geometries
  - Maps TfL severity to blue-purple-red scale for visualization
  - Returns GeoJSON FeatureCollection with 24 real London road corridors

- **Bounding Box Visualization**:
  - Added `DetectionOverlay` component to display bounding boxes on camera feeds
  - Color-coded boxes by object type (car, bus, person, bicycle, etc.)
  - Labels show object name and confidence score
  - Applied to both tactical panel and map marker popups

- **Visual Feedback for Chatbot**:
  - Pulsing animation on collapsed chat bubble when agent is processing
  - "Thinking..." text indicator with animated dots
  - Typing indicator in expanded chat panel
  - Visual feedback appears for both text queries and tool calls

### Changed
- **Nemotron LLM Integration**:
  - Fixed model name to `nemotron_3_nano_omni`
  - Corrected URL to `http://127.0.0.1:8000/v1`
  - Modified `agent.py` to skip OpenClaw in local mode
  - Agent now uses Nemotron directly with tool context injection
  - Removed dependency on OpenClaw subprocess for local agent mode

- **Backend Configuration**:
  - Set `DISRUPTRON_WATCHER=1` to enable autonomous watcher
  - Set `WATCH_INTERVAL_S=30` for demo (increase to 300 for production)
  - Set `DISRUPTRON_PUSH_HOST=0.0.0.0` for remote access
  - Backend now binds to all interfaces for remote connections

- **Frontend Layout**:
  - Fixed chat bubble positioning from absolute to fixed
  - Updated AppShell to use `h-full` for proper height propagation
  - Chatbot box now has broader width and dynamic layout

- **Heatflow Visualization**:
  - Replaced simulated static data with real TfL congestion API
  - Added `fetchRealCongestionData()` function to fetch from backend
  - Added `getFlowPaths()` with fallback to static data if API fails
  - Modified `FlowParticleLayer` to load real data asynchronously
  - Particles now flow along actual TfL road corridors with real-time congestion levels

- **Error Handling**:
  - Added defensive validation for all Date object creations
  - Added timestamp validation in notification components
  - Added date string validation in summaries component
  - Added ttlMs validation in tactical panel provider
  - Added try-catch blocks for async data loading in flow layer
  - All date/time errors now return "Invalid date/time" instead of crashing

### Fixed
- **RENDER FAILURE Invalid time value error**: 
  - Root cause: Invalid timestamps being passed to Date constructor
  - Solution: Added validation checks before creating Date objects
  - Affected files: NotificationToasts, NotificationsView, SummariesView, TacticalPanelProvider, useLiveSession, flowLayer

- **Nemotron not returning text responses**:
  - Root cause: Backend configured for "agent" mode relying on OpenClaw
  - Solution: Modified agent to skip OpenClaw when in local mode
  - Nemotron now used directly for responses and tool calls

- **Backend not reloading .env changes**:
  - Solution: Explicitly killed and restarted backend process
  - Used export commands in restart script to propagate environment variables

- **Watcher environment variable misconfiguration**:
  - Root cause: Set `DISRUPTRON_WATCHER_ENABLED` instead of `DISRUPTRON_WATCHER`
  - Solution: Corrected to `DISRUPTRON_WATCHER=1` in .env

### Technical Details

#### Backend Architecture
- **Gateway (`gateway.py`)**:
  - Added `/v1/geo/road-congestion` endpoint
  - Enhanced lifespan to start watcher loop based on `DISRUPTRON_WATCHER`
  - Added logging for watcher startup confirmation

- **Agent (`agent.py`)**:
  - Modified `AgentChatEngine.ask()` to conditionally call OpenClaw
  - When `self._local` is true, skips OpenClaw execution
  - Forces Nemotron usage with tool context injection

- **Watcher (`watcher.py`)**:
  - Runs in background asyncio task
  - Rotates through JamCam registry deterministically
  - Emits detection events for cameras with ≥1 detection
  - Emits panel events for tactical UI updates
  - Checks TfL for severe disruptions and emits alerts

#### Frontend Architecture
- **Flow Layer (`flowLayer.ts`)**:
  - Added real-time TfL data fetching
  - Implemented fallback to static data on API failure
  - Particles colored by congestion level (blue=low, purple=medium, red=high)
  - Particle speed adjusted by congestion severity

- **Map Page (`MapPage.tsx`)**:
  - Added DetectionOverlay for bounding boxes
  - Updated map marker popups with bounding box overlays
  - Color-coded labels for different object types
  - Always-active heatflow layer for congestion visualization

- **Event Handling (`useLiveSession.ts`)**:
  - Added detection event handler
  - Validates ttlMs before passing to pushDetection
  - Pushes tactical panels for detection events
  - Handles route, panel, and detection event types

#### Configuration
- **Environment Variables**:
  ```
  NEMOTRON_URL=http://127.0.0.1:8000/v1
  NEMOTRON_MODEL=nemotron_3_nano_omni
  DISRUPTRON_PUSH_HOST=0.0.0.0
  DISRUPTRON_WATCHER=1
  WATCH_INTERVAL_S=30
  ```

- **Ports**:
  - Backend: 8010
  - Nemotron vLLM: 8000
  - OpenClaw: 18789 (not used in local mode)

### Testing
- Verified Nemotron direct API returns text responses
- Tested backend chat stream for text events
- Confirmed watcher logs show startup and camera checking
- Verified watcher emits detection events to frontend
- Tested bounding box visualization on camera feeds
- Confirmed real TfL congestion data returns 24 road corridors
- Validated error handling prevents crashes on invalid dates

### Migration Notes
- No breaking changes to existing API endpoints
- Frontend automatically falls back to static data if TfL API fails
- Watcher can be disabled by setting `DISRUPTRON_WATCHER=0`
- Increase `WATCH_INTERVAL_S` to 300 for production (currently 30 for demo)

### Dependencies
- LocateAnything-3B for object detection
- Nemotron 3 Nano Omni for LLM responses
- TfL Unified API for real-time congestion data
- MapLibre GL for map rendering
- Framer Motion for animations
