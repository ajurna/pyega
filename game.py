"""EGATrek game logic — pure Python, no UI dependencies."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GALAXY_SIZE = 8
SECTOR_SIZE = 8

INITIAL_ENERGY = 3000
INITIAL_TORPEDOES = 10
MAX_SHIELDS = 2500

KLINGON_HEALTH = 300
KLINGON_ATTACK_MIN = 50
KLINGON_ATTACK_MAX = 200

IMPULSE_ENERGY_COST = 20
WARP_ENERGY_PER_QUADRANT = 100  # energy per quadrant of distance


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


@dataclass
class Position:
    row: int  # 0-indexed, 0–7
    col: int  # 0-indexed, 0–7

    def distance_to(self, other: "Position") -> float:
        return math.sqrt((self.row - other.row) ** 2 + (self.col - other.col) ** 2)

    def is_adjacent_to(self, other: "Position") -> bool:
        return abs(self.row - other.row) <= 1 and abs(self.col - other.col) <= 1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return self.row == other.row and self.col == other.col

    def __hash__(self) -> int:
        return hash((self.row, self.col))


@dataclass
class Klingon:
    pos: Position
    health: int = KLINGON_HEALTH

    @property
    def is_alive(self) -> bool:
        return self.health > 0


@dataclass
class SystemDamage:
    warp_engines: int = 0
    impulse_engines: int = 0
    phaser_control: int = 0
    torpedo_tubes: int = 0
    shield_control: int = 0
    long_range_sensors: int = 0
    damage_control: int = 0

    SYSTEMS: dict[str, str] = field(default_factory=lambda: {
        "warp_engines": "Warp Engines",
        "impulse_engines": "Impulse Engines",
        "phaser_control": "Phaser Control",
        "torpedo_tubes": "Torpedo Tubes",
        "shield_control": "Shield Control",
        "long_range_sensors": "Long Range Sensors",
        "damage_control": "Damage Control",
    })

    def is_damaged(self, system: str) -> bool:
        return getattr(self, system, 0) > 0

    def repair_tick(self) -> None:
        """Reduce all damage counters by 1 (simulates in-flight auto-repair)."""
        for sys in list(self.SYSTEMS.keys()):
            val = getattr(self, sys)
            if val > 0:
                setattr(self, sys, val - 1)

    def take_hit(self, system: str, amount: int = 2) -> None:
        current = getattr(self, system, 0)
        setattr(self, system, current + amount)

    def all_systems(self) -> list[tuple[str, str, int]]:
        """Returns list of (key, display_name, damage_level)."""
        return [(k, v, getattr(self, k)) for k, v in self.SYSTEMS.items()]


# ---------------------------------------------------------------------------
# Quadrant
# ---------------------------------------------------------------------------


@dataclass
class Quadrant:
    klingons: list[Klingon] = field(default_factory=list)
    starbases: list[Position] = field(default_factory=list)
    stars: list[Position] = field(default_factory=list)
    scanned: bool = False

    @property
    def klingon_count(self) -> int:
        return len(self.klingons)

    @property
    def starbase_count(self) -> int:
        return len(self.starbases)

    @property
    def star_count(self) -> int:
        return len(self.stars)

    def lrs_code(self) -> str:
        k = min(self.klingon_count, 9)
        b = min(self.starbase_count, 9)
        s = min(self.star_count, 9)
        return f"{k}{b}{s}"

    def occupied_positions(self) -> set[tuple[int, int]]:
        occupied: set[tuple[int, int]] = set()
        for k in self.klingons:
            occupied.add((k.pos.row, k.pos.col))
        for b in self.starbases:
            occupied.add((b.row, b.col))
        for s in self.stars:
            occupied.add((s.row, s.col))
        return occupied

    def random_free_pos(self, exclude: Optional[set[tuple[int, int]]] = None) -> Optional[Position]:
        occupied = self.occupied_positions()
        if exclude:
            occupied |= exclude
        free = [(r, c) for r in range(SECTOR_SIZE) for c in range(SECTOR_SIZE) if (r, c) not in occupied]
        if not free:
            return None
        r, c = random.choice(free)
        return Position(r, c)

    def get_display(self) -> dict[tuple[int, int], tuple[str, str]]:
        """Returns {(row, col): (symbol, entity_type)} for rendering."""
        display: dict[tuple[int, int], tuple[str, str]] = {}
        for s in self.stars:
            display[(s.row, s.col)] = ("*", "star")
        for b in self.starbases:
            display[(b.row, b.col)] = ("B", "starbase")
        for k in self.klingons:
            display[(k.pos.row, k.pos.col)] = ("K", "klingon")
        return display


# ---------------------------------------------------------------------------
# Galaxy
# ---------------------------------------------------------------------------


class Galaxy:
    def __init__(self) -> None:
        self.quadrants: list[list[Quadrant]] = [
            [Quadrant() for _ in range(GALAXY_SIZE)] for _ in range(GALAXY_SIZE)
        ]

    @classmethod
    def generate(cls, num_klingons: int = 15, num_starbases: int = 4) -> "Galaxy":
        g = cls()

        # Stars: 1–6 per quadrant
        for row in g.quadrants:
            for q in row:
                n = random.randint(1, 6)
                occupied: set[tuple[int, int]] = set()
                for _ in range(n):
                    free = [(r, c) for r in range(8) for c in range(8) if (r, c) not in occupied]
                    if free:
                        r, c = random.choice(free)
                        q.stars.append(Position(r, c))
                        occupied.add((r, c))

        # Starbases: one per quadrant, spread across galaxy
        placed = 0
        attempts = 0
        while placed < num_starbases and attempts < 500:
            attempts += 1
            qr, qc = random.randint(0, 7), random.randint(0, 7)
            q = g.quadrants[qr][qc]
            if q.starbase_count == 0:
                pos = q.random_free_pos()
                if pos:
                    q.starbases.append(pos)
                    placed += 1

        # Klingons: max 3 per quadrant
        placed = 0
        attempts = 0
        while placed < num_klingons and attempts < 1000:
            attempts += 1
            qr, qc = random.randint(0, 7), random.randint(0, 7)
            q = g.quadrants[qr][qc]
            if q.klingon_count < 3:
                pos = q.random_free_pos()
                if pos:
                    q.klingons.append(Klingon(pos=pos))
                    placed += 1

        return g

    @property
    def total_klingons(self) -> int:
        return sum(q.klingon_count for row in self.quadrants for q in row)

    @property
    def total_starbases(self) -> int:
        return sum(q.starbase_count for row in self.quadrants for q in row)


# ---------------------------------------------------------------------------
# Game State
# ---------------------------------------------------------------------------


class GameState:
    def __init__(self, num_klingons: int = 15, num_starbases: int = 4, stardates: int = 25) -> None:
        self.galaxy = Galaxy.generate(num_klingons, num_starbases)
        self.stardate = float(stardates)
        self.initial_klingons = num_klingons

        # Find a safe starting quadrant (no klingons preferred)
        self.q_pos = self._find_safe_start()
        self.s_pos = Position(3, 3)
        self._fix_player_pos()
        self.current_quadrant.scanned = True

        # Ship stats
        self.energy = INITIAL_ENERGY
        self.torpedoes = INITIAL_TORPEDOES
        self.shields = 0
        self.damage = SystemDamage()
        self.docked = False

        self.game_over = False
        self.won = False
        self.messages: list[str] = []

        self._msg(f"Stardate {self.stardate:.1f}. Destroy {num_klingons} Klingon vessels before time runs out.")
        self._msg(f"Starbases available: {self.galaxy.total_starbases}. Type 'help' for commands.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_safe_start(self) -> Position:
        safe = [
            Position(r, c)
            for r in range(GALAXY_SIZE)
            for c in range(GALAXY_SIZE)
            if self.galaxy.quadrants[r][c].klingon_count == 0
        ]
        return random.choice(safe) if safe else Position(random.randint(0, 7), random.randint(0, 7))

    def _fix_player_pos(self) -> None:
        occupied = self.current_quadrant.occupied_positions()
        if (self.s_pos.row, self.s_pos.col) in occupied:
            pos = self.current_quadrant.random_free_pos()
            if pos:
                self.s_pos = pos

    @property
    def current_quadrant(self) -> Quadrant:
        return self.galaxy.quadrants[self.q_pos.row][self.q_pos.col]

    @property
    def condition(self) -> str:
        if self.docked:
            return "DOCKED"
        if self.current_quadrant.klingon_count > 0:
            return "RED"
        if self.energy < 300:
            return "YELLOW"
        return "GREEN"

    def _msg(self, text: str) -> None:
        self.messages.append(text)

    def _check_end(self) -> None:
        if self.galaxy.total_klingons == 0:
            self.game_over = True
            self.won = True
            self._msg("ALL KLINGONS DESTROYED! Mission accomplished, Captain!")
        elif self.stardate <= 0:
            self.game_over = True
            self._msg(f"TIME'S UP! {self.galaxy.total_klingons} Klingon ships remain. The Federation falls.")
        elif self.energy <= 0:
            self.game_over = True
            self._msg("SHIP'S ENERGY DEPLETED! The Enterprise is lost.")

    def _klingon_attack(self) -> None:
        if self.docked:
            return
        for k in self.current_quadrant.klingons:
            dist = max(0.1, k.pos.distance_to(self.s_pos))
            raw = random.randint(KLINGON_ATTACK_MIN, KLINGON_ATTACK_MAX)
            dmg = int(raw / dist)

            shield_abs = min(self.shields, dmg // 2)
            self.shields = max(0, self.shields - shield_abs)
            hull = dmg - shield_abs
            self.energy = max(0, self.energy - hull)

            self._msg(
                f"  Klingon ({k.pos.row + 1},{k.pos.col + 1}) fires {dmg} units."
                f" Shields -{shield_abs}, Hull -{hull}."
            )

            if hull > 30 and random.random() < 0.35:
                sys_key = random.choice(list(self.damage.SYSTEMS.keys()))
                self.damage.take_hit(sys_key)
                self._msg(f"  >> {self.damage.SYSTEMS[sys_key]} damaged!")

            if self.energy <= 0:
                return

    def _dock(self) -> None:
        self.docked = True
        self.energy = INITIAL_ENERGY
        self.torpedoes = INITIAL_TORPEDOES
        self.shields = 0
        for sys_key in list(self.damage.SYSTEMS.keys()):
            setattr(self.damage, sys_key, 0)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def get_sector_display(self) -> dict[tuple[int, int], tuple[str, str]]:
        """Full display including player ship."""
        display = self.current_quadrant.get_display()
        display[(self.s_pos.row, self.s_pos.col)] = ("E", "ship")
        return display

    def get_galaxy_display(self) -> list[list[tuple[str, bool, bool]]]:
        """8×8 list of (lrs_code_or_???, is_current, is_scanned)."""
        result = []
        for r in range(GALAXY_SIZE):
            row = []
            for c in range(GALAXY_SIZE):
                q = self.galaxy.quadrants[r][c]
                is_current = r == self.q_pos.row and c == self.q_pos.col
                code = q.lrs_code() if q.scanned else "???"
                row.append((code, is_current, q.scanned))
            result.append(row)
        return result

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def cmd_warp(self, qr: int, qc: int) -> list[str]:
        """Warp to quadrant (qr, qc) — 0-indexed."""
        if self.damage.is_damaged("warp_engines"):
            return ["Warp engines are damaged! Reach a starbase for repairs."]
        if not (0 <= qr <= 7 and 0 <= qc <= 7):
            return ["Invalid quadrant (coordinates must be 1–8)."]
        if qr == self.q_pos.row and qc == self.q_pos.col:
            return ["Already in that quadrant. Use 'mov' to move within a sector."]

        dist = max(1, abs(qr - self.q_pos.row) + abs(qc - self.q_pos.col))
        cost = dist * WARP_ENERGY_PER_QUADRANT
        available = self.energy - self.shields

        if available < cost:
            return [f"Insufficient energy. Need {cost}, have {available} (shields: {self.shields})."]

        self.energy -= cost
        self.docked = False
        self.q_pos = Position(qr, qc)

        pos = self.current_quadrant.random_free_pos()
        self.s_pos = pos if pos else Position(3, 3)
        self.current_quadrant.scanned = True
        self.stardate -= dist * 0.5

        msgs = [
            f"Warped to quadrant ({qr + 1},{qc + 1}), sector ({self.s_pos.row + 1},{self.s_pos.col + 1}).",
            f"Energy: {self.energy}  Stardate: {self.stardate:.1f}",
        ]
        k = self.current_quadrant.klingon_count
        if k:
            msgs.append(f"WARNING: {k} Klingon vessel(s) detected! RED ALERT!")

        self.damage.repair_tick()
        for m in msgs:
            self._msg(m)
        self._klingon_attack()
        self._check_end()
        return msgs

    def cmd_impulse(self, sr: int, sc: int) -> list[str]:
        """Impulse move to sector (sr, sc) — 0-indexed."""
        if self.damage.is_damaged("impulse_engines"):
            return ["Impulse engines are damaged!"]
        if not (0 <= sr <= 7 and 0 <= sc <= 7):
            return ["Invalid sector (coordinates must be 1–8)."]

        available = self.energy - self.shields
        if available < IMPULSE_ENERGY_COST:
            return [f"Insufficient energy for impulse ({IMPULSE_ENERGY_COST} needed)."]

        display = self.current_quadrant.get_display()
        target = display.get((sr, sc))
        if target:
            sym, _ = target
            if sym == "*":
                return ["Cannot navigate into a star!"]
            if sym == "K":
                return ["Sector occupied by Klingon vessel!"]

        self.energy -= IMPULSE_ENERGY_COST
        self.s_pos = Position(sr, sc)
        self.stardate -= 0.1
        self.docked = False

        msgs = [f"Moved to sector ({sr + 1},{sc + 1})."]

        for base in self.current_quadrant.starbases:
            if self.s_pos.is_adjacent_to(base):
                self._dock()
                msgs.append("Docked with starbase. Energy, torpedoes, shields replenished. Systems repaired.")
                break

        for m in msgs:
            self._msg(m)

        if not self.docked:
            self._klingon_attack()
        self._check_end()
        return msgs

    def cmd_phasers(self, power: int) -> list[str]:
        if self.damage.is_damaged("phaser_control"):
            return ["Phaser control is damaged!"]
        if power <= 0:
            return ["Invalid power level."]

        available = self.energy - self.shields
        if power > available:
            return [f"Insufficient energy. Available: {available}."]

        klingons = self.current_quadrant.klingons
        if not klingons:
            return ["No Klingon vessels in this quadrant!"]

        self.energy -= power
        self.stardate -= 0.1
        per_k = power / len(klingons)

        msgs = [f"Firing phasers at {power} units ({len(klingons)} targets)..."]
        killed: list[Klingon] = []

        for k in klingons:
            dist = max(0.5, k.pos.distance_to(self.s_pos))
            hit = int(per_k * random.uniform(0.7, 1.3) / dist)
            k.health -= hit
            msgs.append(f"  Klingon ({k.pos.row + 1},{k.pos.col + 1}): {hit} hit, health {max(0, k.health)}.")
            if k.health <= 0:
                killed.append(k)
                msgs.append("  >>> Klingon vessel DESTROYED!")

        for k in killed:
            self.current_quadrant.klingons.remove(k)

        for m in msgs:
            self._msg(m)
        self._klingon_attack()
        self._check_end()
        return msgs

    def cmd_torpedo(self, tr: int, tc: int) -> list[str]:
        """Fire torpedo at sector (tr, tc) — 0-indexed."""
        if self.damage.is_damaged("torpedo_tubes"):
            return ["Torpedo tubes are damaged!"]
        if self.torpedoes <= 0:
            return ["No torpedoes remaining!"]
        if not (0 <= tr <= 7 and 0 <= tc <= 7):
            return ["Invalid torpedo target."]

        self.torpedoes -= 1
        self.stardate -= 0.1

        msgs = [f"Torpedo fired at sector ({tr + 1},{tc + 1})..."]
        display = self.current_quadrant.get_display()
        target = display.get((tr, tc))
        hit = False

        if target:
            sym, _ = target
            if sym == "K":
                for k in self.current_quadrant.klingons:
                    if k.pos.row == tr and k.pos.col == tc:
                        self.current_quadrant.klingons.remove(k)
                        msgs.append("DIRECT HIT! Klingon vessel destroyed!")
                        hit = True
                        break
            elif sym == "B":
                self.current_quadrant.starbases = [
                    b for b in self.current_quadrant.starbases if not (b.row == tr and b.col == tc)
                ]
                msgs.append("WARNING: Friendly starbase destroyed! Starfleet is displeased.")
                hit = True
            elif sym == "*":
                msgs.append("Torpedo absorbed by star.")
                hit = True

        if not hit:
            msgs.append("Torpedo missed! No impact detected.")

        for m in msgs:
            self._msg(m)
        self._klingon_attack()
        self._check_end()
        return msgs

    def cmd_shields(self, level: int) -> list[str]:
        if self.damage.is_damaged("shield_control"):
            return ["Shield control is damaged!"]

        level = max(0, level)
        max_possible = min(MAX_SHIELDS, self.energy + self.shields)
        level = min(level, max_possible)

        delta = level - self.shields
        self.energy -= delta
        self.shields = level

        msg = f"Shields set to {self.shields}. Energy: {self.energy}."
        self._msg(msg)
        return [msg]

    def cmd_lrs(self) -> list[str]:
        if self.damage.is_damaged("long_range_sensors"):
            return ["Long range sensors are damaged!"]

        msgs = ["Long Range Scan (KBS = Klingons/Starbases/Stars):"]
        qr, qc = self.q_pos.row, self.q_pos.col

        for dr in range(-1, 2):
            parts = []
            for dc in range(-1, 2):
                nr, nc = qr + dr, qc + dc
                if 0 <= nr < GALAXY_SIZE and 0 <= nc < GALAXY_SIZE:
                    q = self.galaxy.quadrants[nr][nc]
                    q.scanned = True
                    code = q.lrs_code()
                    marker = f"[{code}]" if (dr == 0 and dc == 0) else f" {code} "
                    parts.append(marker)
                else:
                    parts.append(" --- ")
            msgs.append("  " + " | ".join(parts))

        msgs.append("[] = current quadrant")
        for m in msgs:
            self._msg(m)
        return msgs

    def cmd_dam(self) -> list[str]:
        msgs = ["Damage Report:"]
        for key, name, level in self.damage.all_systems():
            status = "Operational" if level == 0 else f"DAMAGED ({level} repair turns)"
            msgs.append(f"  {name}: {status}")
        for m in msgs:
            self._msg(m)
        return msgs

    def cmd_dock(self) -> list[str]:
        for base in self.current_quadrant.starbases:
            if self.s_pos.is_adjacent_to(base):
                self._dock()
                msg = "Docked with starbase. All systems replenished and repaired."
                self._msg(msg)
                return [msg]
        return ["No starbase in docking range. Move adjacent to a starbase (B)."]

    def cmd_status(self) -> list[str]:
        msgs = [
            "Status Report:",
            f"  Stardate       : {self.stardate:.1f}",
            f"  Condition      : {self.condition}",
            f"  Energy         : {self.energy}",
            f"  Shields        : {self.shields}",
            f"  Torpedoes      : {self.torpedoes}",
            f"  Klingons left  : {self.galaxy.total_klingons}",
            f"  Starbases left : {self.galaxy.total_starbases}",
            f"  Quadrant       : ({self.q_pos.row + 1},{self.q_pos.col + 1})",
            f"  Sector         : ({self.s_pos.row + 1},{self.s_pos.col + 1})",
        ]
        for m in msgs:
            self._msg(m)
        return msgs

    def cmd_help(self) -> list[str]:
        msgs = [
            "COMMAND REFERENCE:",
            "  warp QR QC   Warp to quadrant row/col (1–8)",
            "  mov  SR SC   Impulse move to sector row/col (1–8)",
            "  pha  POWER   Fire phasers with POWER energy units",
            "  tor  TR TC   Fire torpedo at sector row/col (1–8)",
            "  she  LEVEL   Set shield energy level (0 = drain)",
            "  lrs          Long range scan (3×3 quadrant view)",
            "  dam          Damage report",
            "  dock         Dock with adjacent starbase",
            "  status       Full status report",
            "  help         This message",
            "  quit         Surrender",
            "Abbreviations: w p t m s l d",
        ]
        for m in msgs:
            self._msg(m)
        return msgs


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

_ALIASES: dict[str, str] = {
    "w": "warp", "nav": "warp",
    "m": "mov", "imp": "mov", "impulse": "mov",
    "p": "pha", "phaser": "pha", "phasers": "pha",
    "t": "tor", "torp": "tor", "torpedo": "tor",
    "s": "she", "shield": "she", "shields": "she",
    "l": "lrs", "scan": "lrs",
    "d": "dam", "damage": "dam",
    "h": "help", "?": "help",
    "q": "quit", "surrender": "quit",
    "st": "status",
}


def parse_and_execute(state: GameState, raw: str) -> list[str]:
    """Parse a raw command string and execute it. Returns list of message strings."""
    parts = raw.strip().lower().split()
    if not parts:
        return []

    verb = _ALIASES.get(parts[0], parts[0])
    args = parts[1:]

    def get_coord(idx: int) -> Optional[int]:
        """Return 0-indexed coordinate from 1-indexed user input."""
        try:
            v = int(args[idx])
            return v - 1
        except (IndexError, ValueError):
            return None

    def get_int(idx: int) -> Optional[int]:
        try:
            return int(args[idx])
        except (IndexError, ValueError):
            return None

    if state.game_over:
        return ["Game is over. Start a new game."]

    if verb == "warp":
        qr, qc = get_coord(0), get_coord(1)
        if qr is None or qc is None:
            return ["Usage: warp <quadrant-row> <quadrant-col>  (e.g. warp 3 4)"]
        return state.cmd_warp(qr, qc)

    if verb == "mov":
        sr, sc = get_coord(0), get_coord(1)
        if sr is None or sc is None:
            return ["Usage: mov <sector-row> <sector-col>  (e.g. mov 5 3)"]
        return state.cmd_impulse(sr, sc)

    if verb == "pha":
        power = get_int(0)
        if power is None:
            return ["Usage: pha <energy>  (e.g. pha 500)"]
        return state.cmd_phasers(power)

    if verb == "tor":
        tr, tc = get_coord(0), get_coord(1)
        if tr is None or tc is None:
            return ["Usage: tor <sector-row> <sector-col>  (e.g. tor 3 5)"]
        return state.cmd_torpedo(tr, tc)

    if verb == "she":
        level = get_int(0)
        if level is None:
            return ["Usage: she <level>  (e.g. she 500)"]
        return state.cmd_shields(level)

    if verb == "lrs":
        return state.cmd_lrs()

    if verb == "dam":
        return state.cmd_dam()

    if verb == "dock":
        return state.cmd_dock()

    if verb == "status":
        return state.cmd_status()

    if verb == "help":
        return state.cmd_help()

    if verb == "quit":
        state.game_over = True
        state._msg("You have surrendered. The Federation mourns your cowardice.")
        return ["Surrender accepted."]

    msg = f"Unknown command '{parts[0]}'. Type 'help' for commands."
    state._msg(msg)
    return [msg]
