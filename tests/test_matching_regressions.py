import unittest

from knowledge_base import reset_cache
from rules import analyze


class MatchingRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_battery_oral_hygiene_surfaces_household_safety_reviews_without_lvd(self) -> None:
        result = analyze("battery-powered oral hygiene appliance")

        self.assertNotIn("LVD", result.directives)
        review_codes = {item.code for item in result.review_items}
        self.assertIn("EN 60335-1", review_codes)
        self.assertIn("EN 60335-2-52", review_codes)

    def test_electric_tooth_brush_normalizes_to_oral_hygiene_route(self) -> None:
        result = analyze("electric tooth brush")

        self.assertEqual(result.product_type, "oral_hygiene_appliance")
        review_codes = {item.code for item in result.review_items}
        self.assertIn("EN 60335-1", review_codes)
        self.assertIn("EN 60335-2-52", review_codes)

    def test_smart_toothbrush_stays_on_oral_hygiene_route(self) -> None:
        result = analyze("smart toothbrush with bluetooth and app control")

        self.assertIn(result.product_type, {"battery_powered_oral_hygiene", "oral_hygiene_appliance"})
        self.assertNotEqual(result.product_type, "home_projector")
        codes = {item.code for item in result.standards + result.review_items}
        self.assertIn("EN 60335-2-52", codes)
        self.assertNotIn("EN 62368-1", codes)

    def test_robot_lawn_mower_aliases_share_the_same_safety_route(self) -> None:
        robot = analyze("robot lawn mower")
        robotic = analyze("robotic lawn mower")

        self.assertEqual(robot.product_type, "robotic_lawn_mower")
        self.assertEqual(robotic.product_type, "robotic_lawn_mower")
        self.assertIn("EN 50636-2-107", {item.code for item in robot.standards})
        self.assertIn("EN 50636-2-107", {item.code for item in robotic.standards})
        self.assertIn("EN 60335-2-107", {item.code for item in robot.review_items})

    def test_battery_av_ict_product_keeps_62368_as_review_when_lvd_is_absent(self) -> None:
        result = analyze("Digital audio player / DAC")

        self.assertNotIn("LVD", result.directives)
        self.assertIn("EN 62368-1", {item.code for item in result.review_items})

    def test_smart_watch_prefers_av_ict_routes_over_appliance_emc(self) -> None:
        result = analyze("smart watch")

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}
        all_codes = standard_codes | review_codes

        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_fitness_tracker_prefers_av_ict_routes_over_appliance_emc(self) -> None:
        result = analyze("fitness tracker")

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}
        all_codes = standard_codes | review_codes

        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_smart_ring_prefers_av_ict_routes_over_appliance_emc(self) -> None:
        result = analyze("smart ring")

        standard_codes = {item.code for item in result.standards}
        review_codes = {item.code for item in result.review_items}
        all_codes = standard_codes | review_codes

        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)
        self.assertIn("EN 62368-1", standard_codes)
        self.assertNotIn("EN 55014-1", all_codes)
        self.assertNotIn("EN 55014-2", all_codes)

    def test_hair_dryer_no_longer_selects_conflicting_part2_routes(self) -> None:
        result = analyze("hair dryer")

        codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertIn("EN 60335-1", {item.code for item in result.standards})
        self.assertIn("EN 60335-2-23", {item.code for item in result.standards})
        self.assertNotIn("EN 60335-2-45", codes)

    def test_curling_iron_reaches_the_hair_care_part2_route(self) -> None:
        result = analyze("curling iron")

        self.assertIn("EN 60335-1", {item.code for item in result.standards})
        self.assertIn("EN 60335-2-23", {item.code for item in result.standards})

    def test_family_level_projector_keeps_62368_route(self) -> None:
        result = analyze("portable projector")

        standard_codes = {item.code for item in result.standards}
        self.assertIn("EN 62368-1", standard_codes)
        self.assertIn("EN 55032", standard_codes)
        self.assertIn("EN 55035", standard_codes)

    def test_ambiguous_security_camera_still_surfaces_62368_review(self) -> None:
        result = analyze("security camera")

        codes = {item.code for item in result.standards} | {item.code for item in result.review_items}
        self.assertIn("EN 62368-1", codes)

    def test_video_doorbell_surfaces_62368_review_from_product_candidates(self) -> None:
        result = analyze("video doorbell")

        review_codes = {item.code for item in result.review_items}
        self.assertIn("EN 62368-1", review_codes)


if __name__ == "__main__":
    unittest.main()
