from __future__ import annotations

from .base import subtype_case

GROUP = "kitchen_beverage"

CASES = (
    subtype_case(GROUP, "air_fryer_digital", "digital air fryer with basket and timer", "air_fryer"),
    subtype_case(GROUP, "barbecue_grill_tabletop", "electric barbecue grill with removable plate", "barbecue_grill"),
    subtype_case(GROUP, "blender_smoothie", "smoothie blender with glass jug", "blender"),
    subtype_case(GROUP, "coffee_grinder_burr", "burr coffee grinder with grind selector", "coffee_grinder"),
    subtype_case(GROUP, "coffee_machine_bean_to_cup", "bean to cup coffee machine with milk frother", "coffee_machine"),
    subtype_case(GROUP, "electric_kettle_temp_control", "electric kettle with temperature control", "electric_kettle"),
    subtype_case(GROUP, "food_processor_multifunction", "multifunction food processor with slicing disc", "food_processor"),
    subtype_case(GROUP, "microwave_oven_countertop", "countertop microwave oven with grill", "microwave_oven"),
    subtype_case(GROUP, "oven_fan_forced", "built in oven with convection fan and digital timer", "oven"),
    subtype_case(GROUP, "range_hood_chimney", "chimney range hood with led lighting", "range_hood"),
    subtype_case(GROUP, "refrigerator_freezer_frost_free", "frost free refrigerator freezer with bottom freezer", "refrigerator_freezer"),
    subtype_case(GROUP, "rice_cooker_keep_warm", "rice cooker with keep warm mode", "rice_cooker"),
    subtype_case(GROUP, "smart_food_scale_wifi", "smart food scale with nutrition app and wifi", "smart_food_scale"),
    subtype_case(GROUP, "smart_food_thermometer_probe", "smart food thermometer with wireless probe", "smart_food_thermometer"),
    subtype_case(GROUP, "sous_vide_cooker_precision", "precision sous vide cooker with immersion clip", "sous_vide_cooker"),
    subtype_case(GROUP, "toaster_four_slice", "4 slice toaster with browning control", "toaster"),
)
