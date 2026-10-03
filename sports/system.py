"""
pairwise-sports-system - SportsSystem

Physics / rules / AI / scoring engine for a sports game.
"""

import math


GRAVITY = 9.81
AIR_DENSITY = 1.225
DEFAULT_DRAG_COEFFICIENT = 0.25
DEFAULT_MAGNUS_COEFFICIENT = 0.15
DEFAULT_RESTITUTION = 0.6
DEFAULT_FRICTION = 0.4


class SportsSystem:
    def __init__(self):
        self.state = {}

    # ------------------------------------------------------------------
    # Ball physics: air drag + spin (Magnus curve) + bounce
    # ------------------------------------------------------------------
    def calculate_ball_physics(self, position=None, velocity=None, spin=None,
                               dt=0.016, mass=0.45, radius=0.11,
                               drag_coefficient=DEFAULT_DRAG_COEFFICIENT,
                               magnus_coefficient=DEFAULT_MAGNUS_COEFFICIENT,
                               restitution=DEFAULT_RESTITUTION,
                               ground_friction=DEFAULT_FRICTION,
                               ground_y=0.0, steps=1):
        position = list(position) if position is not None else [0.0, 1.0, 0.0]
        velocity = list(velocity) if velocity is not None else [10.0, 5.0, 0.0]
        spin = list(spin) if spin is not None else [0.0, 0.0, 0.0]

        area = math.pi * radius * radius
        drag_factor = 0.5 * AIR_DENSITY * drag_coefficient * area / mass
        magnus_factor = magnus_coefficient * area / mass

        trajectory = [tuple(position)]
        bounced = False

        for _ in range(max(1, steps)):
            speed = math.sqrt(sum(v * v for v in velocity))

            # Air resistance: opposes motion, scales with v^2.
            drag = [-drag_factor * speed * v for v in velocity]

            # Magnus lift from spin: force ~ spin x velocity (curve balls).
            magnus = [
                magnus_factor * (spin[1] * velocity[2] - spin[2] * velocity[1]),
                magnus_factor * (spin[2] * velocity[0] - spin[0] * velocity[2]),
                magnus_factor * (spin[0] * velocity[1] - spin[1] * velocity[0]),
            ]

            accel = [drag[0] + magnus[0],
                     drag[1] + magnus[1] - GRAVITY,
                     drag[2] + magnus[2]]

            velocity = [velocity[i] + accel[i] * dt for i in range(3)]
            position = [position[i] + velocity[i] * dt for i in range(3)]

            # Bounce off the ground with restitution + tangential friction.
            if position[1] - radius <= ground_y and velocity[1] < 0.0:
                position[1] = ground_y + radius
                velocity[1] = -velocity[1] * restitution
                velocity[0] *= (1.0 - ground_friction)
                velocity[2] *= (1.0 - ground_friction)
                bounced = True

            trajectory.append(tuple(position))

        speed = math.sqrt(sum(v * v for v in velocity))
        return {
            "position": tuple(position),
            "velocity": tuple(velocity),
            "speed": speed,
            "spin": tuple(spin),
            "trajectory": trajectory,
            "bounced": bounced,
            "drag_applied": True,
            "magnus_applied": any(abs(s) > 0.0 for s in spin),
        }

    # ------------------------------------------------------------------
    # Player physics: collision + inertia + center of gravity
    # ------------------------------------------------------------------
    def update_player_physics(self, players=None, dt=0.016,
                              player_radius=0.4, restitution=0.3,
                              inertia=0.9, com_height=1.0,
                              max_lean_angle=45.0):
        if players is None:
            players = [
                {"id": 0, "position": [0.0, 0.0], "velocity": [3.0, 0.0],
                 "desired_velocity": [3.0, 0.0], "mass": 75.0},
                {"id": 1, "position": [0.5, 0.0], "velocity": [-3.0, 0.0],
                 "desired_velocity": [-3.0, 0.0], "mass": 75.0},
            ]
        players = [dict(p) for p in players]
        for p in players:
            p.setdefault("position", [0.0, 0.0])
            p.setdefault("velocity", [0.0, 0.0])
            p.setdefault("desired_velocity", list(p["velocity"]))
            p.setdefault("mass", 75.0)
            p["position"] = list(p["position"])
            p["velocity"] = list(p["velocity"])

        collisions = []
        fallen = []

        # Inertia: velocity eases toward desired velocity instead of
        # stopping/turning instantly.
        for p in players:
            for i in range(2):
                p["velocity"][i] = (inertia * p["velocity"][i]
                                    + (1.0 - inertia) * p["desired_velocity"][i])
            p["position"][0] += p["velocity"][0] * dt
            p["position"][1] += p["velocity"][1] * dt

        # Circle-vs-circle collision resolution (no passing through).
        min_dist = 2.0 * player_radius
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                a, b = players[i], players[j]
                dx = b["position"][0] - a["position"][0]
                dy = b["position"][1] - a["position"][1]
                dist = math.hypot(dx, dy)
                if dist < min_dist:
                    nx, ny = (dx / dist, dy / dist) if dist > 1e-9 else (1.0, 0.0)
                    overlap = min_dist - dist
                    # Positional separation.
                    a["position"][0] -= nx * overlap / 2.0
                    a["position"][1] -= ny * overlap / 2.0
                    b["position"][0] += nx * overlap / 2.0
                    b["position"][1] += ny * overlap / 2.0
                    # Impulse exchange along the normal.
                    ma, mb = a["mass"], b["mass"]
                    va = a["velocity"][0] * nx + a["velocity"][1] * ny
                    vb = b["velocity"][0] * nx + b["velocity"][1] * ny
                    va2 = (va * (ma - restitution * mb) + (1 + restitution) * mb * vb) / (ma + mb)
                    vb2 = (vb * (mb - restitution * ma) + (1 + restitution) * ma * va) / (ma + mb)
                    for p, before, after in ((a, va, va2), (b, vb, vb2)):
                        p["velocity"][0] += (after - before) * nx
                        p["velocity"][1] += (after - before) * ny
                    collisions.append((a.get("id", i), b.get("id", j)))

        # Center of gravity: sharp high-speed turns topple the player.
        for idx, p in enumerate(players):
            speed = math.hypot(*p["velocity"])
            desired = p["desired_velocity"]
            desired_speed = math.hypot(*desired)
            if speed > 1e-6 and desired_speed > 1e-6:
                dot = (p["velocity"][0] * desired[0]
                       + p["velocity"][1] * desired[1]) / (speed * desired_speed)
                turn_angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
            else:
                turn_angle = 0.0
            # Lateral acceleration tilts the body; past max lean it falls.
            lateral_g = 0.0
            if speed > 1e-6 and turn_angle > 0.0:
                lateral_g = speed * math.radians(turn_angle) / max(dt, 1e-6) / GRAVITY
            lean = math.degrees(math.atan2(lateral_g * com_height, 1.0)) if lateral_g else 0.0
            p["lean_angle"] = lean
            p["fallen"] = lean > max_lean_angle
            if p["fallen"]:
                fallen.append(p.get("id", idx))
                p["velocity"] = [v * 0.5 for v in p["velocity"]]

        return {
            "players": players,
            "collisions": collisions,
            "fallen": fallen,
            "inertia_applied": True,
            "collision_applied": True,
            "center_of_gravity_applied": True,
        }

    # ------------------------------------------------------------------
    # Game rules: out of bounds + fouls + match clock
    # ------------------------------------------------------------------
    def check_game_rules(self, ball_position=None, field=None, events=None,
                         clock=None, half_duration=45.0 * 60.0, halves=2):
        field = field or {"x_min": -52.5, "x_max": 52.5,
                          "y_min": -34.0, "y_max": 34.0}
        ball_position = ball_position or [0.0, 0.0]
        events = events or []
        clock = dict(clock) if clock else {"time": 0.0, "half": 1, "running": True}

        out_of_bounds = None
        if ball_position[0] < field["x_min"] or ball_position[0] > field["x_max"]:
            out_of_bounds = "goal_line"
        elif ball_position[1] < field["y_min"] or ball_position[1] > field["y_max"]:
            out_of_bounds = "touchline"

        fouls = []
        for event in events:
            kind = event.get("type")
            if kind in ("push", "trip", "hold", "kick", "handball", "charge"):
                fouls.append({
                    "type": kind,
                    "player": event.get("player"),
                    "victim": event.get("victim"),
                    "card": event.get("card"),
                    "whistle": True,
                })

        match_length = half_duration * halves
        clock["time"] = min(clock.get("time", 0.0), match_length)
        clock["half"] = min(int(clock["time"] // half_duration) + 1, halves)
        match_over = clock["time"] >= match_length
        if match_over:
            clock["running"] = False

        whistle = out_of_bounds is not None or bool(fouls) or match_over
        return {
            "out_of_bounds": out_of_bounds,
            "fouls": fouls,
            "clock": clock,
            "match_over": match_over,
            "whistle": whistle,
        }

    # ------------------------------------------------------------------
    # AI: tactics + passing + defense
    # ------------------------------------------------------------------
    def update_ai_player(self, ai_player=None, teammates=None, opponents=None,
                         ball=None, goal=None, dt=0.016,
                         pass_distance=25.0, mark_distance=2.0):
        ai_player = dict(ai_player) if ai_player else {
            "id": 10, "position": [0.0, 0.0], "has_ball": True, "role": "midfielder",
        }
        ai_player.setdefault("position", [0.0, 0.0])
        ai_player.setdefault("has_ball", False)
        teammates = teammates if teammates is not None else [
            {"id": 7, "position": [15.0, 5.0]},
            {"id": 9, "position": [20.0, -8.0]},
        ]
        opponents = opponents if opponents is not None else [
            {"id": 4, "position": [3.0, 1.0]},
        ]
        ball = ball or {"position": list(ai_player["position"]), "owner": ai_player.get("id")}
        goal = goal or {"position": [52.5, 0.0]}

        action = {"type": "hold", "target": None}

        if ai_player.get("has_ball"):
            # Tactic: if pressured, pass to the best-placed teammate instead
            # of dribbling forever.
            pressure = min(
                (math.dist(ai_player["position"], o["position"]) for o in opponents),
                default=float("inf"),
            )
            best_mate = None
            best_score = -float("inf")
            for mate in teammates:
                dist = math.dist(ai_player["position"], mate["position"])
                goal_dist = math.dist(mate["position"], goal["position"])
                score = -goal_dist - 0.2 * dist
                if dist <= pass_distance and score > best_score:
                    best_score = score
                    best_mate = mate
            if pressure < 3.0 and best_mate is not None:
                action = {"type": "pass", "target": best_mate.get("id"),
                          "target_position": list(best_mate["position"])}
                ai_player["has_ball"] = False
            else:
                # Dribble toward goal as the default tactic.
                gx, gy = goal["position"]
                px, py = ai_player["position"]
                dx, dy = gx - px, gy - py
                norm = math.hypot(dx, dy) or 1.0
                speed = 5.0
                ai_player["position"] = [px + dx / norm * speed * dt,
                                         py + dy / norm * speed * dt]
                action = {"type": "dribble", "target": "goal",
                          "direction": [dx / norm, dy / norm]}
        else:
            # Defense: mark the nearest opponent / chase the ball carrier.
            nearest = None
            nearest_dist = float("inf")
            for opp in opponents:
                d = math.dist(ai_player["position"], opp["position"])
                if d < nearest_dist:
                    nearest, nearest_dist = opp, d
            if nearest is not None:
                px, py = ai_player["position"]
                tx, ty = nearest["position"]
                dx, dy = tx - px, ty - py
                norm = math.hypot(dx, dy) or 1.0
                if nearest_dist > mark_distance:
                    speed = 6.0
                    ai_player["position"] = [px + dx / norm * speed * dt,
                                             py + dy / norm * speed * dt]
                action = {"type": "mark", "target": nearest.get("id"),
                          "distance": nearest_dist}

        return {
            "player": ai_player,
            "action": action,
            "tactic": "pass_when_pressed" if ai_player.get("has_ball") else "mark_nearest",
            "passing_enabled": True,
            "defense_enabled": True,
        }

    # ------------------------------------------------------------------
    # Scoring: validation + replay review + stats
    # ------------------------------------------------------------------
    def update_score(self, event=None, score=None, stats=None,
                     replay_available=True, goal_line=None, offside=False):
        score = dict(score) if score else {"home": 0, "away": 0}
        stats = stats if stats is not None else {"scorers": [], "shots": {}}
        stats.setdefault("scorers", [])
        stats.setdefault("shots", {})
        event = event or {
            "type": "goal", "team": "home", "scorer": 9,
            "ball_position": [53.0, 0.0], "minute": 12.0,
        }
        goal_line = goal_line if goal_line is not None else 52.5

        validation = {"valid": False, "reason": None}
        replay = {"used": False, "decision": None}

        if event.get("type") != "goal":
            validation["reason"] = "not_a_goal_event"
        elif offside:
            validation["reason"] = "offside"
        else:
            ball_x = event.get("ball_position", [0.0, 0.0])[0]
            if ball_x <= goal_line:
                validation["reason"] = "ball_not_over_line"
            else:
                validation["valid"] = True

        # Controversial calls go to replay review.
        if not validation["valid"] and replay_available and event.get("type") == "goal":
            replay["used"] = True
            ball_x = event.get("ball_position", [0.0, 0.0])[0]
            if ball_x > goal_line and not offside:
                validation = {"valid": True, "reason": "confirmed_by_replay"}
                replay["decision"] = "goal_confirmed"
            else:
                replay["decision"] = "goal_disallowed"

        if validation["valid"]:
            team = event.get("team", "home")
            score[team] = score.get(team, 0) + 1
            scorer = event.get("scorer")
            stats["scorers"].append({
                "player": scorer,
                "team": team,
                "minute": event.get("minute"),
            })
            stats["shots"][scorer] = stats["shots"].get(scorer, 0) + 1

        return {
            "score": score,
            "validation": validation,
            "replay": replay,
            "stats": stats,
        }
