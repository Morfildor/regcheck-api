from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "household_core"

CASES = (
    subtype_case(GROUP, "dishwasher_built_in", "built in dishwasher with delay start and adjustable racks", "dishwasher", forbidden_subtypes=("commercial_dishwasher",)),
    subtype_case(GROUP, "commercial_dishwasher_pass_through", "commercial dishwasher pass-through under counter", "commercial_dishwasher", forbidden_subtypes=("dishwasher",), tags=("contrastive",)),
    subtype_case(GROUP, "exercise_bike_upright", "upright exercise bike with magnetic resistance", "exercise_bike", forbidden_subtypes=("smart_treadmill", "elliptical_trainer")),
    subtype_case(GROUP, "elliptical_trainer_resistance", "elliptical trainer with magnetic resistance and heart rate sensor", "elliptical_trainer", forbidden_subtypes=("exercise_bike", "smart_treadmill")),
    subtype_case(GROUP, "washer_dryer_combo", "washer dryer combo with inverter motor and drying cycle", "washer_dryer", forbidden_subtypes=("washing_machine", "tumble_dryer")),
    subtype_case(GROUP, "multicooker_pressure", "multicooker with pressure mode and slow cook mode", "multicooker", forbidden_subtypes=("slow_cooker", "rice_cooker")),
    subtype_case(GROUP, "slow_cooker_ceramic", "programmable slow cooker with ceramic pot", "slow_cooker", forbidden_subtypes=("multicooker", "rice_cooker")),
    subtype_case(GROUP, "bread_maker_kneading", "automatic bread maker with kneading paddle", "bread_maker", forbidden_subtypes=("multicooker",)),
    subtype_case(GROUP, "air_cooler_evaporative", "portable evaporative air cooler with water tank", "air_cooler"),
    subtype_case(GROUP, "bottle_sterilizer_steam", "baby bottle steam sterilizer", "bottle_sterilizer"),
    subtype_case(GROUP, "food_waste_disposer_continuous", "under sink food waste disposer with continuous feed", "food_waste_disposer"),
    family_case(GROUP, "water_dispenser_plumbed", "plumbed water dispenser with hot and cold water", "water_dispensing_appliance", tags=("boundary",)),
)
