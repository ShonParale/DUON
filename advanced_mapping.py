"""
DUON — Advanced Mapping Module
Handles map lifecycle, obstacle CRUD, live sonar heat-mapping,
and autonomous exploration / A-to-B navigation for the Mapping page.
No changes to ESP1/ESP2 firmware or existing features.
"""

import heapq
import json
import math
import os
import threading
import time
import uuid

MAPS_DIR  = "maps"
GRID_RES  = 20   # cm per A* grid cell
GRID_PAD  = 1    # cells of safety padding around obstacles


class AdvancedMapManager:
    SPEED_CM_S   = 18.0   # estimated forward speed cm/s
    TURN_90_MS   = 480    # ms for a 90-degree turn
    FRONT_THR    = 35     # explore/nav front obstacle threshold cm
    DIAG_THR     = 25     # explore diagonal threshold cm
    PULSE_MS     = 400    # explore forward pulse ms
    SETTLE_MS    = 350    # settle after stop ms

    def __init__(self, broadcast_fn):
        self._broadcast = broadcast_fn
        os.makedirs(MAPS_DIR, exist_ok=True)

        # ── Active map state ──────────────────────────────────────
        self.active_map  = None
        self.room_width  = 400.0
        self.room_height = 400.0
        self.resolution  = 10
        self.obstacles   = []
        self.heat_map    = []
        self._heat_max   = 800

        # ── Robot pose (dead-reckoning) ───────────────────────────
        self.bot_x    = 0.0
        self.bot_y    = 0.0
        self.heading  = 0.0   # degrees, 0 = North (+Y)

        # ── Live sonar values ─────────────────────────────────────
        self._sonar_L = 380.0
        self._sonar_F = 380.0
        self._sonar_R = 380.0

        # ── Drive tracking for dead-reckoning ─────────────────────
        self._drive_cmd   = 'X'
        self._drive_start = time.time()
        self._drive_lock  = threading.Lock()

        # ── Explore state ─────────────────────────────────────────
        self._exploring = False

        # ── Navigation state ──────────────────────────────────────
        self._navigating = False
        self.nav_target  = None    # [tx, ty]
        self.nav_path    = []      # [[x, y], ...] planned path for canvas

        # ── Periodic state broadcast ──────────────────────────────
        threading.Thread(target=self._bcast_loop, daemon=True).start()

    # ═══════════════════════════════════════════════════════════
    # SONAR & POSE FEED  (called externally)
    # ═══════════════════════════════════════════════════════════

    def update_sonar(self, L, F, R):
        """Called from Robot._parse_sonar — feed live sonar values."""
        self._sonar_L = L
        self._sonar_F = F
        self._sonar_R = R
        if self.active_map:
            self._project_heat()

    def on_drive_cmd(self, cmd):
        """Called when a drive command is sent to the robot."""
        with self._drive_lock:
            self._flush_motion()
            self._drive_cmd   = cmd
            self._drive_start = time.time()

    # ═══════════════════════════════════════════════════════════
    # DEAD-RECKONING INTERNALS
    # ═══════════════════════════════════════════════════════════

    def _flush_motion(self):
        """Integrate elapsed motion into pose before switching command."""
        elapsed = time.time() - self._drive_start
        cmd     = self._drive_cmd
        if cmd == 'W':
            r = math.radians(self.heading)
            d = elapsed * self.SPEED_CM_S
            self.bot_x += d * math.sin(r)
            self.bot_y += d * math.cos(r)
        elif cmd == 'S':
            r = math.radians(self.heading)
            d = elapsed * self.SPEED_CM_S
            self.bot_x -= d * math.sin(r)
            self.bot_y -= d * math.cos(r)
        elif cmd == 'A':
            dps = 90.0 / (self.TURN_90_MS / 1000.0)
            self.heading = (self.heading - dps * elapsed) % 360
        elif cmd == 'D':
            dps = 90.0 / (self.TURN_90_MS / 1000.0)
            self.heading = (self.heading + dps * elapsed) % 360
        self.bot_x = max(0.0, min(self.room_width,  self.bot_x))
        self.bot_y = max(0.0, min(self.room_height, self.bot_y))
        self._drive_start = time.time()

    def _project_heat(self):
        """Project sonar rays onto the map as heat-map points."""
        for dist, angle_deg in [
            (self._sonar_L, -45),
            (self._sonar_F,   0),
            (self._sonar_R,  45),
        ]:
            if dist < 375:
                r  = math.radians(self.heading + angle_deg)
                hx = self.bot_x + dist * math.sin(r)
                hy = self.bot_y + dist * math.cos(r)
                pt = [round(hx / 5) * 5, round(hy / 5) * 5]
                if pt not in self.heat_map:
                    self.heat_map.append(pt)
        if len(self.heat_map) > self._heat_max:
            self.heat_map = self.heat_map[-self._heat_max:]

    # ═══════════════════════════════════════════════════════════
    # HEAT MAP
    # ═══════════════════════════════════════════════════════════

    def clear_heat(self):
        self.heat_map = []
        self._push_state()

    # ═══════════════════════════════════════════════════════════
    # ROOM SIZE
    # ═══════════════════════════════════════════════════════════

    def set_room(self, width, height):
        self.room_width  = max(50.0, float(width))
        self.room_height = max(50.0, float(height))
        self._push_state()

    # ═══════════════════════════════════════════════════════════
    # BOT POSITION (manual set by user)
    # ═══════════════════════════════════════════════════════════

    def set_bot_pos(self, x, y, heading=None):
        """Let user manually set where the bot starts in the room."""
        with self._drive_lock:
            self._flush_motion()
            self.bot_x = float(x)
            self.bot_y = float(y)
            if heading is not None:
                self.heading = float(heading) % 360
            self._drive_cmd   = 'X'
            self._drive_start = time.time()
        self._push_state()
        self._broadcast({'type': 'log', 'msg': f'[MAPPING] Bot position set to ({x:.0f}, {y:.0f}) h={self.heading:.0f}°'})

    # ═══════════════════════════════════════════════════════════
    # OBSTACLE CRUD
    # ═══════════════════════════════════════════════════════════

    def add_obstacle(self, name, x1, y1, x2, y2):
        obs = {
            'id':   str(uuid.uuid4())[:8],
            'name': str(name),
            'x1': float(x1), 'y1': float(y1),
            'x2': float(x2), 'y2': float(y2),
        }
        self.obstacles.append(obs)
        self._push_state()
        return obs

    def update_obstacle(self, obs_id, name, x1, y1, x2, y2):
        for obs in self.obstacles:
            if obs['id'] == obs_id:
                obs.update({
                    'name': str(name),
                    'x1': float(x1), 'y1': float(y1),
                    'x2': float(x2), 'y2': float(y2),
                })
                break
        self._push_state()

    def remove_obstacle(self, obs_id):
        self.obstacles = [o for o in self.obstacles if o['id'] != obs_id]
        self._push_state()

    # ═══════════════════════════════════════════════════════════
    # MAP LIFECYCLE
    # ═══════════════════════════════════════════════════════════

    def list_maps(self):
        if not os.path.isdir(MAPS_DIR):
            return []
        return sorted(f[:-5] for f in os.listdir(MAPS_DIR) if f.endswith('.json'))

    def new_map(self, name):
        self._reset_state()
        self.active_map = name.strip()
        self.save_map()
        self._push_state()
        self._broadcast({'type': 'log', 'msg': f'[MAPPING] New map created: {name}'})

    def load_map(self, name):
        path = os.path.join(MAPS_DIR, name + '.json')
        if not os.path.exists(path):
            self._broadcast({'type': 'log', 'msg': f'[MAPPING] Map not found: {name}'})
            return False
        try:
            with open(path) as f:
                data = json.load(f)
            self.active_map  = name
            self.room_width  = float(data.get('width',  400))
            self.room_height = float(data.get('height', 400))
            self.resolution  = int(data.get('resolution', 10))
            self.obstacles   = data.get('obstacles', [])
            self.heat_map    = data.get('heat_map', [])
            self._push_state()
            self._broadcast({'type': 'log', 'msg': f'[MAPPING] Map loaded: {name}'})
            return True
        except Exception as e:
            self._broadcast({'type': 'log', 'msg': f'[MAPPING] Load error: {e}'})
            return False

    def save_map(self):
        if not self.active_map:
            self._broadcast({'type': 'log', 'msg': '[MAPPING] No active map to save.'})
            return False
        os.makedirs(MAPS_DIR, exist_ok=True)
        path = os.path.join(MAPS_DIR, self.active_map + '.json')
        data = {
            'width':      self.room_width,
            'height':     self.room_height,
            'resolution': self.resolution,
            'obstacles':  self.obstacles,
            'heat_map':   self.heat_map,
        }
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            self._broadcast({'type': 'log', 'msg': f'[MAPPING] Saved: {self.active_map}'})
            return True
        except Exception as e:
            self._broadcast({'type': 'log', 'msg': f'[MAPPING] Save error: {e}'})
            return False

    def close_map(self):
        name = self.active_map
        self._reset_state()
        self._push_state()
        self._broadcast({'type': 'log', 'msg': f'[MAPPING] Map closed (file kept): {name}'})

    def delete_map(self, name):
        path = os.path.join(MAPS_DIR, name + '.json')
        try:
            if os.path.exists(path):
                os.remove(path)
            if self.active_map == name:
                self._reset_state()
            self._push_state()
            self._broadcast({'type': 'log', 'msg': f'[MAPPING] Deleted: {name}'})
            return True
        except Exception as e:
            self._broadcast({'type': 'log', 'msg': f'[MAPPING] Delete error: {e}'})
            return False

    def _reset_state(self):
        self.active_map  = None
        self.room_width  = 400.0
        self.room_height = 400.0
        self.resolution  = 10
        self.obstacles   = []
        self.heat_map    = []
        self.bot_x = self.bot_y = self.heading = 0.0
        self.nav_path   = []
        self.nav_target = None
        with self._drive_lock:
            self._drive_cmd   = 'X'
            self._drive_start = time.time()

    # ═══════════════════════════════════════════════════════════
    # AUTONOMOUS EXPLORATION  (Method 3 — real robot)
    # ═══════════════════════════════════════════════════════════

    def start_explore(self, robot):
        if self._exploring:
            return
        self._exploring = True
        threading.Thread(target=self._explore_loop, args=(robot,), daemon=True).start()
        self._broadcast({'type': 'log', 'msg': '[MAPPING] Autonomous exploration started.'})

    def stop_explore(self, robot):
        self._exploring = False
        robot.raw_send('X')
        self.on_drive_cmd('X')
        self._push_state()
        self._broadcast({'type': 'log', 'msg': '[MAPPING] Autonomous exploration stopped.'})

    def _explore_loop(self, robot):
        """Reactive exploration — same proven logic as AutoMapper, uses raw_send."""
        self._broadcast({'type': 'log', 'msg': '[EXPLORE] Loop started'})
        while self._exploring:
            try:
                L, F, R = self._sonar_L, self._sonar_F, self._sonar_R
                ft, dt  = self.FRONT_THR, self.DIAG_THR

                if F > ft and L > dt and R > dt:
                    # Forward pulse
                    robot.raw_send('W'); self.on_drive_cmd('W')
                    time.sleep(self.PULSE_MS / 1000)
                    robot.raw_send('X'); self.on_drive_cmd('X')
                    time.sleep(self.SETTLE_MS / 1000)
                elif F > ft and R <= dt:
                    robot.raw_send('A'); self.on_drive_cmd('A')
                    time.sleep(self.PULSE_MS / 1000)
                    robot.raw_send('X'); self.on_drive_cmd('X')
                    time.sleep(self.SETTLE_MS / 1000)
                elif F > ft and L <= dt:
                    robot.raw_send('D'); self.on_drive_cmd('D')
                    time.sleep(self.PULSE_MS / 1000)
                    robot.raw_send('X'); self.on_drive_cmd('X')
                    time.sleep(self.SETTLE_MS / 1000)
                elif F <= ft:
                    if R > ft:
                        turn = 'D'
                    elif L > ft:
                        turn = 'A'
                    else:
                        # U-turn: two 90° rights
                        for _ in range(2):
                            robot.raw_send('D'); self.on_drive_cmd('D')
                            time.sleep(self.TURN_90_MS / 1000)
                            robot.raw_send('X'); self.on_drive_cmd('X')
                            time.sleep(200 / 1000)
                        continue
                    robot.raw_send(turn); self.on_drive_cmd(turn)
                    time.sleep(self.TURN_90_MS / 1000)
                    robot.raw_send('X'); self.on_drive_cmd('X')
                    time.sleep(self.SETTLE_MS / 1000)
            except Exception as e:
                self._broadcast({'type': 'log', 'msg': f'[EXPLORE ERR] {e}'})
                time.sleep(0.5)

        robot.raw_send('X')
        self.on_drive_cmd('X')
        self._push_state()
        self._broadcast({'type': 'log', 'msg': '[EXPLORE] Stopped'})

    # ═══════════════════════════════════════════════════════════
    # A* PATHFINDING + NAVIGATION  (A→B)
    # ═══════════════════════════════════════════════════════════

    def _build_grid(self):
        """Build occupancy grid from obstacles with safety padding."""
        cols = int(math.ceil(self.room_width  / GRID_RES)) + 4
        rows = int(math.ceil(self.room_height / GRID_RES)) + 4
        grid = [[False] * rows for _ in range(cols)]
        for obs in self.obstacles:
            x1 = min(obs['x1'], obs['x2'])
            y1 = min(obs['y1'], obs['y2'])
            x2 = max(obs['x1'], obs['x2'])
            y2 = max(obs['y1'], obs['y2'])
            gx1 = max(0, int(x1 / GRID_RES) - GRID_PAD)
            gy1 = max(0, int(y1 / GRID_RES) - GRID_PAD)
            gx2 = min(cols - 1, int(x2 / GRID_RES) + GRID_PAD + 1)
            gy2 = min(rows - 1, int(y2 / GRID_RES) + GRID_PAD + 1)
            for gx in range(gx1, gx2 + 1):
                for gy in range(gy1, gy2 + 1):
                    grid[gx][gy] = True
        return grid, cols, rows

    def _astar(self, grid, cols, rows, sx, sy, gx, gy):
        """A* search. Returns list of (col, row) grid cells."""
        def heur(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        start = (sx, sy)
        goal  = (gx, gy)
        # If goal is blocked, find nearest free cell
        if grid[gx][gy]:
            best, best_d = None, 9999
            for dc in range(-2, 3):
                for dr in range(-2, 3):
                    nc, nr = gx + dc, gy + dr
                    if 0 <= nc < cols and 0 <= nr < rows and not grid[nc][nr]:
                        d = abs(dc) + abs(dr)
                        if d < best_d:
                            best, best_d = (nc, nr), d
            if best:
                goal = best
            else:
                return []

        open_set  = [(0, start)]
        came_from = {}
        g_score   = {start: 0.0}
        dirs = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]

        while open_set:
            _, cur = heapq.heappop(open_set)
            if cur == goal:
                path = []
                while cur in came_from:
                    path.append(cur)
                    cur = came_from[cur]
                path.append(start)
                return list(reversed(path))
            for dc, dr in dirs:
                nb = (cur[0] + dc, cur[1] + dr)
                if not (0 <= nb[0] < cols and 0 <= nb[1] < rows):
                    continue
                if grid[nb[0]][nb[1]]:
                    continue
                step = 1.414 if dc and dr else 1.0
                tent = g_score[cur] + step
                if tent < g_score.get(nb, float('inf')):
                    came_from[nb] = cur
                    g_score[nb]   = tent
                    f = tent + heur(nb, goal)
                    heapq.heappush(open_set, (f, nb))
        return []  # no path found

    def _plan_path(self, tx, ty):
        """Build grid, run A*, convert to world-coord waypoints."""
        grid, cols, rows = self._build_grid()
        sx = max(0, min(cols - 1, int(self.bot_x / GRID_RES)))
        sy = max(0, min(rows - 1, int(self.bot_y / GRID_RES)))
        gx = max(0, min(cols - 1, int(tx / GRID_RES)))
        gy = max(0, min(rows - 1, int(ty / GRID_RES)))
        cell_path = self._astar(grid, cols, rows, sx, sy, gx, gy)
        # Convert grid cells to world cm (cell centre)
        return [[c * GRID_RES + GRID_RES // 2,
                 r * GRID_RES + GRID_RES // 2] for c, r in cell_path]

    def _move_to_waypoint(self, robot, wx, wy):
        """Turn to face waypoint then move forward to it."""
        dx   = wx - self.bot_x
        dy   = wy - self.bot_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < GRID_RES * 0.6:
            return  # already close enough

        # Compute needed heading (atan2: x=east=right, y=north=up)
        target_h = math.degrees(math.atan2(dx, dy)) % 360
        diff     = (target_h - self.heading + 180) % 360 - 180  # -180..+180

        # Turn
        if abs(diff) > 8:
            turn_ms = int(abs(diff) / 90.0 * self.TURN_90_MS)
            turn_ms = max(50, turn_ms)
            cmd     = 'D' if diff > 0 else 'A'
            robot.raw_send(cmd)
            time.sleep(turn_ms / 1000.0)
            robot.raw_send('X')
            time.sleep(self.SETTLE_MS / 1000.0)
            self.heading = target_h

        # Move forward
        move_ms = int(dist / self.SPEED_CM_S * 1000)
        move_ms = min(move_ms, self.PULSE_MS * 4)  # cap to ~4 pulses max
        robot.raw_send('W')
        self.on_drive_cmd('W')
        time.sleep(move_ms / 1000.0)
        robot.raw_send('X')
        self.on_drive_cmd('X')
        time.sleep(self.SETTLE_MS / 1000.0)

    def _navigate_loop(self, robot, tx, ty):
        """Execute A→B navigation with dynamic obstacle avoidance."""
        self._navigating = True
        self.nav_target  = [tx, ty]
        self._broadcast({'type': 'log', 'msg': f'[NAV] Planning path to ({tx:.0f}, {ty:.0f} cm)'})

        try:
            path = self._plan_path(tx, ty)
            if not path:
                self._broadcast({'type': 'log', 'msg': '[NAV] No path found — check obstacles or target position'})
                return

            self.nav_path = path
            self._push_state()
            self._broadcast({'type': 'log', 'msg': f'[NAV] Path found: {len(path)} waypoints'})

            wp_idx = 1  # skip first waypoint (current position)
            while self._navigating and wp_idx < len(path):
                wx, wy = path[wp_idx]

                # ── Dynamic obstacle check before each move ──────────
                if self._sonar_F < self.FRONT_THR:
                    self._broadcast({'type': 'log', 'msg': f'[NAV] Dynamic obstacle ahead (F={self._sonar_F:.0f}cm) — avoiding'})
                    # Simple avoidance: turn away from the blocked side
                    if self._sonar_R > self._sonar_L:
                        robot.raw_send('D'); time.sleep(self.TURN_90_MS / 1000)
                    else:
                        robot.raw_send('A'); time.sleep(self.TURN_90_MS / 1000)
                    robot.raw_send('X'); time.sleep(self.SETTLE_MS / 1000)
                    self.on_drive_cmd('X')

                    # Replan from current position
                    new_path = self._plan_path(tx, ty)
                    if not new_path:
                        self._broadcast({'type': 'log', 'msg': '[NAV] Replan failed — stopping'})
                        break
                    path = new_path
                    self.nav_path = path
                    self._push_state()
                    wp_idx = 1
                    continue

                # ── Move to next waypoint ────────────────────────────
                self._move_to_waypoint(robot, wx, wy)
                self._push_state()
                wp_idx += 1

            if self._navigating:
                self._broadcast({'type': 'log', 'msg': f'[NAV] Reached target ({tx:.0f}, {ty:.0f} cm)'})

        except Exception as e:
            self._broadcast({'type': 'log', 'msg': f'[NAV ERR] {e}'})

        finally:
            self._navigating = False
            self.nav_path    = []
            self.nav_target  = None
            robot.raw_send('X')
            self.on_drive_cmd('X')
            self._push_state()

    def navigate_to(self, robot, tx, ty):
        """Start A→B navigation in background thread."""
        if self._navigating:
            self._broadcast({'type': 'log', 'msg': '[NAV] Already navigating — stop first'})
            return
        if self._exploring:
            self._broadcast({'type': 'log', 'msg': '[NAV] Stop exploration first'})
            return
        threading.Thread(
            target=self._navigate_loop, args=(robot, tx, ty), daemon=True
        ).start()

    def stop_navigate(self, robot):
        """Abort active navigation."""
        self._navigating = False
        robot.raw_send('X')
        self.on_drive_cmd('X')
        self.nav_path   = []
        self.nav_target = None
        self._push_state()
        self._broadcast({'type': 'log', 'msg': '[NAV] Navigation stopped by user'})

    # ═══════════════════════════════════════════════════════════
    # STATE BROADCAST
    # ═══════════════════════════════════════════════════════════

    def _push_state(self):
        with self._drive_lock:
            self._flush_motion()
        self._broadcast(self._state_dict())

    def get_state(self):
        """Full state for new WS connections (includes maps_list)."""
        d = self._state_dict()
        d['maps_list'] = self.list_maps()
        return d

    def _state_dict(self):
        return {
            'type':        'adv_map',
            'active_map':  self.active_map,
            'room_width':  self.room_width,
            'room_height': self.room_height,
            'resolution':  self.resolution,
            'obstacles':   self.obstacles,
            'heat_map':    self.heat_map[-500:],
            'bot':         {'x': self.bot_x, 'y': self.bot_y, 'h': self.heading},
            'exploring':   self._exploring,
            'navigating':  self._navigating,
            'nav_path':    self.nav_path,
            'nav_target':  self.nav_target,
        }

    def _bcast_loop(self):
        """Push live state every 400ms while active."""
        while True:
            time.sleep(0.4)
            if self.active_map or self._exploring or self._navigating:
                self._push_state()
