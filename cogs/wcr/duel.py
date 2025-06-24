from log_setup import get_logger


logger = get_logger(__name__)


class DuelCalculator:
    """Hilfsfunktionen für Mini-Duelle."""

    def scale_stat(self, base: float | int, level: int) -> float:
        """Return ``base`` scaled by +10% per level above 1."""
        if level < 1:
            level = 1
        return base * (1 + 0.1 * (level - 1))

    def scaled_stats(self, unit_data: dict, level: int) -> dict:
        """Return a copy of ``unit_data['stats']`` scaled for ``level``."""
        stats = unit_data.get("stats", {})
        result = {}
        dmg_key = (
            "damage"
            if "damage" in stats
            else "area_damage" if "area_damage" in stats else None
        )
        if dmg_key:
            result[dmg_key] = self.scale_stat(stats[dmg_key], level)
        if "health" in stats:
            result["health"] = self.scale_stat(stats["health"], level)
        attack_speed = stats.get("attack_speed")
        if attack_speed is not None:
            result["attack_speed"] = attack_speed
        if dmg_key and attack_speed:
            result["dps"] = result[dmg_key] / attack_speed
        return result

    def spell_total_damage(self, unit: dict, stats: dict) -> float:
        """Return estimated total damage a spell deals."""
        base_stats = unit.get("stats", {})
        damage = stats.get("damage", stats.get("area_damage", 0))
        if "dps" in stats:
            duration = base_stats.get("duration", 1)
            damage = max(damage, stats["dps"] * duration)
        return damage

    def compute_dps_details(
        self, attacker: dict, attacker_stats: dict, defender: dict
    ) -> tuple[float, list[str]]:
        """Calculate DPS and return notes about trait interactions."""
        notes: list[str] = []
        traits_a = [str(t) for t in attacker.get("trait_ids", [])]
        traits_d = [str(t) for t in defender.get("trait_ids", [])]

        if (
            attacker.get("type_id") != "2"
            and "15" in traits_d
            and "11" not in traits_a
            and "15" not in traits_a
        ):
            notes.append("kann Flieger nicht treffen")
            return 0.0, notes

        dmg_key = (
            "damage"
            if "damage" in attacker_stats
            else "area_damage" if "area_damage" in attacker_stats else None
        )
        if dmg_key is None:
            notes.append("verursacht keinen Schaden")
            return 0.0, notes

        damage = attacker_stats[dmg_key]
        if "8" in traits_a and "20" in traits_d:
            damage *= 0.5
            notes.append("Resistent halbiert Elementarschaden")
        elif "8" not in traits_a and "13" in traits_d:
            damage *= 0.5
            notes.append("Gepanzert halbiert Schaden")

        attack_speed = attacker_stats.get("attack_speed")
        if attack_speed:
            return damage / attack_speed, notes

        if attacker.get("type_id") == 2:
            dps = attacker_stats.get("dps")
            if dps is not None:
                return dps, notes
            return damage, notes

        return attacker_stats.get("dps", 0.0), notes

    def compute_dps(
        self, attacker: dict, attacker_stats: dict, defender: dict
    ) -> float:
        """Backward compatible wrapper around ``compute_dps_details``."""
        dps, _ = self.compute_dps_details(attacker, attacker_stats, defender)
        return dps

    def duel_result(
        self,
        unit_a: dict,
        level_a: int,
        unit_b: dict,
        level_b: int,
    ) -> tuple[str, float] | None:
        """Return (winner_name, time) or None for tie/impossible."""
        stats_a = self.scaled_stats(unit_a, level_a)
        stats_b = self.scaled_stats(unit_b, level_b)

        is_spell_a = unit_a.get("type_id") == "2"
        is_spell_b = unit_b.get("type_id") == "2"

        dps_a = self.compute_dps(unit_a, stats_a, unit_b)
        dps_b = self.compute_dps(unit_b, stats_b, unit_a)

        if is_spell_a and is_spell_b:
            if dps_a == dps_b:
                return None
            return ("a", 0.0) if dps_a > dps_b else ("b", 0.0)

        if is_spell_a:
            total_damage = self.spell_total_damage(unit_a, stats_a)
            if total_damage >= stats_b.get("health", 0):
                return "a", 0.0
            return None

        if is_spell_b:
            total_damage = self.spell_total_damage(unit_b, stats_b)
            if total_damage >= stats_a.get("health", 0):
                return "b", 0.0
            return None

        health_a = stats_a.get("health", 0)
        health_b = stats_b.get("health", 0)

        time_a = health_b / dps_a if dps_a > 0 else float("inf")
        time_b = health_a / dps_b if dps_b > 0 else float("inf")

        if time_a == time_b:
            return None
        if time_a < time_b:
            return "a", time_a
        return "b", time_b
