"""Village skills — occupation-based actions that plug into ARIA's Skill protocol."""

from .farming import FarmingSkill
from .building import BuildingSkill
from .hunting import HuntingSkill
from .trading import TradingSkill
from .blacksmithing import BlacksmithingSkill

VILLAGE_SKILLS = [FarmingSkill, BuildingSkill, HuntingSkill, TradingSkill, BlacksmithingSkill]

__all__ = ["FarmingSkill", "BuildingSkill", "HuntingSkill", "TradingSkill", "BlacksmithingSkill", "VILLAGE_SKILLS"]
