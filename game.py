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

MAX_WARP = 8
DEFAULT_WARP = 5

KLINGON_HEALTH = 300
KLINGON_ATTACK_MIN = 50
KLINGON_ATTACK_MAX = 200

IMPULSE_ENERGY_COST = 20
WARP_ENERGY_PER_QUADRANT = 100  # base energy per quadrant at warp 1
ENERGY_REGEN_PER_STARDATE = 400  # energy produced per stardate elapsed


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
        self.shield_energy: int = 0       # energy stored in the shield pool
        self.shields_up: bool = False     # whether shields are currently raised
        self.warp_factor: float = DEFAULT_WARP
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
    def shields(self) -> int:
        """Backwards-compat alias for shield_energy (used by UI)."""
        return self.shield_energy

    @property
    def shield_efficiency(self) -> float:
        """0.1–1.0 based on shield generator health. Each damage level costs 15%."""
        return max(0.1, 1.0 - self.damage.shield_control * 0.15)

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

            if self.shields_up and self.shield_energy > 0:
                efficiency = self.shield_efficiency
                # Effective protection is pool × efficiency multiplier
                effective = self.shield_energy * efficiency
                if effective >= dmg:
                    # Shields fully absorb — consume proportional pool energy
                    energy_used = int(dmg / efficiency)
                    self.shield_energy = max(0, self.shield_energy - energy_used)
                    shield_abs, hull = dmg, 0
                else:
                    # Partial absorption — drain entire pool, remainder hits hull
                    shield_abs = int(effective)
                    self.shield_energy = 0
                    hull = dmg - shield_abs
            else:
                shield_abs, hull = 0, dmg

            self.energy = max(0, self.energy - hull)
            eff_note = (f" (shields {self.shield_efficiency * 100:.0f}% efficient)"
                        if self.shields_up and self.damage.shield_control > 0 else "")
            self._msg(
                f"  Klingon ({k.pos.row + 1},{k.pos.col + 1}) fires {dmg} units."
                f" Shields absorbed {shield_abs}{eff_note}, Hull -{hull}."
            )

            if hull > 30 and random.random() < 0.35:
                sys_key = random.choice(list(self.damage.SYSTEMS.keys()))
                self.damage.take_hit(sys_key)
                self._msg(f"  >> {self.damage.SYSTEMS[sys_key]} damaged!")

            if self.energy <= 0:
                return

    def _energy_regen(self, stardates_elapsed: float) -> None:
        """Passive reactor power generation proportional to time elapsed.
        Generates ENERGY_REGEN_PER_STARDATE units per stardate at full power;
        half that when warp engines are damaged.
        """
        if self.docked:
            return
        efficiency = 0.5 if self.damage.is_damaged("warp_engines") else 1.0
        regen = int(ENERGY_REGEN_PER_STARDATE * stardates_elapsed * efficiency)
        self.energy = min(INITIAL_ENERGY, self.energy + regen)

    def _dock(self) -> None:
        self.docked = True
        self.energy = INITIAL_ENERGY      # starbase refuels main energy only
        self.torpedoes = INITIAL_TORPEDOES
        # shield_energy and shields_up are unchanged — player transfers manually
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

    def _warp_path(self, dest_qr: int, dest_qc: int) -> list[tuple[int, int]]:
        """Return quadrant coords along the straight-line path to destination, excluding origin."""
        start_r, start_c = self.q_pos.row, self.q_pos.col
        dr = dest_qr - start_r
        dc = dest_qc - start_c
        steps = max(abs(dr), abs(dc))
        path: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for i in range(1, steps + 1):
            r = round(start_r + dr * i / steps)
            c = round(start_c + dc * i / steps)
            if (r, c) not in seen:
                path.append((r, c))
                seen.add((r, c))
        return path

    def cmd_set_warp(self, warp_factor: float) -> list[str]:
        """Set the ship's warp factor for future warp travel."""
        max_warp = MAX_WARP / 2 if self.damage.is_damaged("warp_engines") else MAX_WARP
        warp_factor = max(0.1, min(float(warp_factor), max_warp))
        self.warp_factor = warp_factor
        msg = f"Warp factor set to {warp_factor:.1f}."
        if self.damage.is_damaged("warp_engines"):
            msg += f" (Max {max_warp:.0f} — engines damaged.)"
        self._msg(msg)
        return [msg]

    def cmd_move(
        self,
        qr: int | None,
        qc: int | None,
        sr: int | None,
        sc: int | None,
    ) -> list[str]:
        """Unified move command — mirrors the original EGATrek 'm' command.

        Impulse (within current quadrant): provide only sr, sc.
        Warp (to another quadrant):        provide qr, qc (and optionally sr, sc).

        Warp uses self.warp_factor set by cmd_set_warp().
        Energy at warp = warp_factor × WARP_ENERGY_PER_QUADRANT per quadrant.
        Shields raised during warp doubles energy cost.
        Time elapsed = 1.0 / warp_factor stardates per quadrant.
        """
        # ---- Impulse move (sector only) ----
        if qr is None or qc is None:
            if sr is None or sc is None:
                return ["Usage: m [QR QC] SR SC  (e.g. m35 or m6235)"]
            if self.damage.is_damaged("impulse_engines"):
                return ["Impulse engines are damaged!"]
            if not (0 <= sr <= 7 and 0 <= sc <= 7):
                return ["Invalid sector (coordinates must be 1–8)."]

            available = self.energy
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
            stardate_cost = 0.1
            self.stardate -= stardate_cost
            self.docked = False

            msgs = [f"Impulse to sector ({sr + 1},{sc + 1}). Energy: {self.energy}"]

            for base in self.current_quadrant.starbases:
                if self.s_pos.is_adjacent_to(base):
                    self._dock()
                    msgs.append("Docked with starbase. Energy, torpedoes, shields replenished. Systems repaired.")
                    break

            self._energy_regen(stardate_cost)
            for m in msgs:
                self._msg(m)
            if not self.docked:
                self._klingon_attack()
            self._check_end()
            return msgs

        # ---- Warp move (to another quadrant) ----
        if self.damage.is_damaged("warp_engines"):
            return ["Warp engines are damaged! Reach a starbase for repairs."]
        if not (0 <= qr <= 7 and 0 <= qc <= 7):
            return ["Invalid quadrant (coordinates must be 1–8)."]
        if sr is not None and not (0 <= sr <= 7):
            return ["Invalid sector row (must be 1–8)."]
        if sc is not None and not (0 <= sc <= 7):
            return ["Invalid sector col (must be 1–8)."]
        if qr == self.q_pos.row and qc == self.q_pos.col:
            return ["Already in that quadrant. Use 'm SR SC' to move within a sector."]

        wf = self.warp_factor
        shield_multiplier = 2.0 if self.shields_up else 1.0
        energy_per_quad = wf * WARP_ENERGY_PER_QUADRANT * shield_multiplier
        time_per_quad = 1.0 / wf

        path = self._warp_path(qr, qc)
        total_dist = len(path)
        total_cost = int(total_dist * energy_per_quad)
        available = self.energy

        if available < total_cost:
            shield_note = " (shields doubled cost)" if shield_multiplier > 1 else ""
            return [
                f"Insufficient energy at warp {wf:.1f}{shield_note}. "
                f"Need {total_cost}, have {available}."
            ]

        self.docked = False
        msgs: list[str] = []

        # Check each intermediate quadrant for Klingon interdiction
        for i, (quad_r, quad_c) in enumerate(path[:-1]):
            q = self.galaxy.quadrants[quad_r][quad_c]
            if q.klingon_count > 0:
                pull_chance = min(0.85, 0.3 * q.klingon_count)
                if random.random() < pull_chance:
                    dist_traveled = i + 1
                    cost = int(dist_traveled * energy_per_quad)
                    stardate_cost = dist_traveled * time_per_quad
                    self.energy = max(0, self.energy - cost)
                    self.stardate -= stardate_cost
                    self.q_pos = Position(quad_r, quad_c)
                    pos = self.current_quadrant.random_free_pos()
                    self.s_pos = pos if pos else Position(3, 3)
                    self.current_quadrant.scanned = True
                    msgs.append(
                        f"Klingons in quadrant ({quad_r + 1},{quad_c + 1}) pull you out of warp!"
                    )
                    msgs.append(
                        f"Dropped into ({quad_r + 1},{quad_c + 1}), "
                        f"sector ({self.s_pos.row + 1},{self.s_pos.col + 1}). "
                        f"Energy: {self.energy}  Stardate: {self.stardate:.1f}"
                    )
                    msgs.append(f"WARNING: {q.klingon_count} Klingon vessel(s) here! RED ALERT!")
                    self.damage.repair_tick()
                    self._energy_regen(stardate_cost)
                    for m in msgs:
                        self._msg(m)
                    self._klingon_attack()
                    self._check_end()
                    return msgs

        # Reached destination
        stardate_cost = total_dist * time_per_quad
        self.energy -= total_cost
        self.stardate -= stardate_cost
        self.q_pos = Position(qr, qc)
        self.current_quadrant.scanned = True

        # Land in requested sector if free, otherwise find a free one
        if sr is not None and sc is not None:
            occupied = self.current_quadrant.occupied_positions()
            self.s_pos = Position(sr, sc) if (sr, sc) not in occupied else (
                self.current_quadrant.random_free_pos() or Position(sr, sc)
            )
        else:
            self.s_pos = self.current_quadrant.random_free_pos() or Position(3, 3)

        shield_note = " (shields active — double energy cost)" if shield_multiplier > 1 else ""
        msgs.append(
            f"Arrived at quadrant ({qr + 1},{qc + 1}), "
            f"sector ({self.s_pos.row + 1},{self.s_pos.col + 1})."
            f"{shield_note}"
        )
        msgs.append(f"Energy: {self.energy}  Stardate: {self.stardate:.1f}")
        k = self.current_quadrant.klingon_count
        if k:
            msgs.append(f"WARNING: {k} Klingon vessel(s) detected! RED ALERT!")

        self.damage.repair_tick()
        self._energy_regen(stardate_cost)
        for m in msgs:
            self._msg(m)
        self._klingon_attack()
        self._check_end()
        return msgs

        if not self.docked:
            self._klingon_attack()
        self._check_end()
        return msgs

    def cmd_phasers(self, power: int) -> list[str]:
        if self.damage.is_damaged("phaser_control"):
            return ["Phaser control is damaged!"]
        if power <= 0:
            return ["Invalid power level."]

        available = self.energy
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

        self._energy_regen(0.1)
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

        self._energy_regen(0.1)
        for m in msgs:
            self._msg(m)
        self._klingon_attack()
        self._check_end()
        return msgs

    SHIELD_RAISE_COST = 50  # one-time energy cost to energise shield generators

    def cmd_shup(self) -> list[str]:
        """Raise shields (SHUP). Small one-time energy cost."""
        if self.damage.is_damaged("shield_control"):
            return ["Shield control is damaged!"]
        if self.shields_up:
            return ["Shields are already raised."]
        if self.energy < self.SHIELD_RAISE_COST:
            return [f"Insufficient energy to raise shields (need {self.SHIELD_RAISE_COST})."]
        self.shields_up = True
        self.energy -= self.SHIELD_RAISE_COST
        msg = (f"Shields raised. Energy -{self.SHIELD_RAISE_COST}. "
               f"Shield energy: {self.shield_energy}. Use 'ene N' to transfer energy to shields.")
        self._msg(msg)
        return [msg]

    def cmd_shdn(self) -> list[str]:
        """Lower shields (SHDN). Free; shield energy pool is retained."""
        if not self.shields_up:
            return ["Shields are already down."]
        self.shields_up = False
        msg = f"Shields lowered. Shield energy pool retained: {self.shield_energy}."
        self._msg(msg)
        return [msg]

    def cmd_energy_transfer(self, amount: int) -> list[str]:
        """Transfer energy between main banks and shield pool.
        Positive amount = main → shields.  Negative = shields → main.
        """
        if self.damage.is_damaged("shield_control"):
            return ["Shield control is damaged — cannot transfer energy to shields."]
        if amount == 0:
            return ["Specify a non-zero transfer amount (e.g. 'ene 500' or 'ene -200')."]

        if amount > 0:
            can = min(amount, self.energy, MAX_SHIELDS - self.shield_energy)
            if can <= 0:
                if self.shield_energy >= MAX_SHIELDS:
                    return [f"Shield energy already at maximum ({MAX_SHIELDS})."]
                return ["Insufficient main energy for transfer."]
            self.energy -= can
            self.shield_energy += can
            msg = f"Transferred {can} to shields. Main: {self.energy}, Shields: {self.shield_energy}."
        else:
            can = min(-amount, self.shield_energy, INITIAL_ENERGY - self.energy)
            if can <= 0:
                return ["No shield energy to transfer back." if self.shield_energy == 0
                        else "Main energy already full."]
            self.shield_energy -= can
            self.energy += can
            msg = f"Transferred {can} from shields to main. Main: {self.energy}, Shields: {self.shield_energy}."

        self._msg(msg)
        return [msg]

    def cmd_max_shields(self) -> list[str]:
        """Divert maximum possible energy from main banks to shield pool."""
        if self.damage.is_damaged("shield_control"):
            return ["Shield control is damaged!"]
        can = min(self.energy, MAX_SHIELDS - self.shield_energy)
        if can <= 0:
            return [f"Shield energy already at maximum ({MAX_SHIELDS})."]
        self.energy -= can
        self.shield_energy += can
        msg = f"Maximum energy diverted to shields. Main: {self.energy}, Shields: {self.shield_energy}."
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
        shield_status = (f"UP  ({self.shield_energy}/{MAX_SHIELDS}, "
                         f"{self.shield_efficiency * 100:.0f}% efficient)"
                         if self.shields_up else
                         f"DOWN ({self.shield_energy} stored)")
        msgs = [
            "Status Report:",
            f"  Stardate       : {self.stardate:.1f}",
            f"  Condition      : {self.condition}",
            f"  Main energy    : {self.energy}",
            f"  Shields        : {shield_status}",
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
            "  m QR QC SR SC  Warp to quadrant+sector (e.g. m 6 2 3 5 or m6235)",
            "  m SR SC        Impulse move within quadrant (e.g. m 3 5 or m35)",
            "  w FACTOR       Set warp factor 0.1–8 (e.g. w5 or w2.5)",
            "  pha  POWER     Fire phasers with POWER energy units",
            "  tor  TR TC     Fire torpedo at sector row/col (1–8)",
            "  shup / s       Raise shields (small energy cost)",
            "  shdn / sd      Lower shields (free; pool energy retained)",
            "  ene  N         Transfer N energy main→shields (neg = shields→main)",
            "  max            Divert max energy to shields",
            "  lrs            Long range scan (3×3 quadrant view)",
            "  dam            Damage report",
            "  dock           Dock with adjacent starbase",
            "  status         Full status report",
            "  help           This message",
            "  quit           Surrender",
        ]
        for m in msgs:
            self._msg(m)
        return msgs


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

_ALIASES: dict[str, str] = {
    "move": "m", "nav": "m", "imp": "m", "impulse": "m",
    "p": "pha", "phaser": "pha", "phasers": "pha",
    "t": "tor", "torp": "tor", "torpedo": "tor",
    "s": "shup", "shield": "shup", "shields": "shup",
    "sd": "shdn",
    "e": "ene", "energy": "ene",
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

    if verb == "w":
        try:
            wf = float(args[0])
        except (IndexError, ValueError):
            return [f"Usage: w <warp-factor>  (e.g. w5 or w2.5, max {MAX_WARP})"]
        return state.cmd_set_warp(wf)

    if verb == "m":
        # Parse compact form: m6235 → qr=6,qc=2,sr=3,sc=5 OR m35 → sr=3,sc=5
        # Also accept space-separated: m 6 2 3 5 or m 3 5
        if len(args) == 0:
            return ["Usage: m [QR QC] SR SC  (e.g.  m 3 5  or  m 6 2 3 5)"]
        if len(args) == 1:
            # Compact form: all digits concatenated
            digits = args[0]
            if not digits.isdigit() or len(digits) not in (2, 4):
                return ["Usage: m QRQCSRSC or m SRSC  (e.g. m6235 or m35)"]
            if len(digits) == 4:
                qr, qc, sr, sc = int(digits[0])-1, int(digits[1])-1, int(digits[2])-1, int(digits[3])-1
            else:
                qr, qc, sr, sc = None, None, int(digits[0])-1, int(digits[1])-1
        elif len(args) == 2:
            qr, qc = None, None
            sr, sc = get_coord(0), get_coord(1)
        elif len(args) == 4:
            qr, qc = get_coord(0), get_coord(1)
            sr, sc = get_coord(2), get_coord(3)
        else:
            return ["Usage: m [QR QC] SR SC  (e.g.  m 3 5  or  m 6 2 3 5)"]
        return state.cmd_move(qr, qc, sr, sc)

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

    if verb == "shup":
        return state.cmd_shup()

    if verb == "shdn":
        return state.cmd_shdn()

    if verb == "ene":
        amount = get_int(0)
        if amount is None:
            return ["Usage: ene <amount>  (e.g. ene 500  or  ene -200 to reclaim)"]
        return state.cmd_energy_transfer(amount)

    if verb == "max":
        return state.cmd_max_shields()

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
