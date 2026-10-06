import unittest

import pandas as pd

from pipeline.schema import COLUMNS
from pipeline.sources import jobspy_source as js


def _jobspy_frame() -> pd.DataFrame:
    """A JobSpy-shaped frame, no network involved."""
    return pd.DataFrame(
        {
            "id": [1, 2],
            "site": ["linkedin", "indeed"],
            "job_url": [
                "https://www.linkedin.com/jobs/view/1234567890",
                "https://co.inindeed.com/viewjob?jk=abc123",
            ],
            "title": ["Analista de Datos", "Contador"],
            "company": ["SA SAS", "SAS SA"],
            "location": ["Bogotá, Cundinamarca, Colombia", "Medellín"],
            "date_posted": ["2026-10-04", None],
            "job_type": ["fulltime", "parttime"],
            "interval": ["yearly", None],
            "min_amount": [4_000_000, None],
            "max_amount": [6_000_000, None],
            "currency": ["COP", None],
            "is_remote": [False, True],
            "description": ["Full text", None],
        }
    )


class ToCanonicalTest(unittest.TestCase):
    def test_maps_to_the_canonical_schema(self):
        out = js.to_canonical(_jobspy_frame())
        self.assertEqual(list(out.columns), COLUMNS)

    def test_source_and_id_come_from_the_job_url(self):
        out = js.to_canonical(_jobspy_frame())
        self.assertEqual(out.iloc[0]["source"], "linkedin")
        self.assertEqual(out.iloc[0]["vacancy_id"], "1234567890")
        self.assertEqual(out.iloc[1]["vacancy_id"], "viewjob")  # no better id in URL

    def test_location_is_split_into_city_and_department(self):
        out = js.to_canonical(_jobspy_frame())
        self.assertEqual(out.iloc[0]["city"], "Bogotá")
        self.assertEqual(out.iloc[0]["department"], "Cundinamarca")
        self.assertEqual(out.iloc[1]["city"], "Medellín")
        self.assertTrue(pd.isna(out.iloc[1]["department"]))

    def test_contract_type_and_modality_are_translated(self):
        out = js.to_canonical(_jobspy_frame())
        self.assertEqual(out.iloc[0]["contract_type"], "Tiempo completo")
        self.assertEqual(out.iloc[1]["contract_type"], "Medio tiempo")
        self.assertEqual(out.iloc[1]["work_modality"], "Remoto")
        self.assertTrue(pd.isna(out.iloc[0]["work_modality"]))

    def test_salary_text_is_built_when_amounts_exist(self):
        out = js.to_canonical(_jobspy_frame())
        self.assertIn("COP", out.iloc[0]["salary_text"])
        self.assertIn("4,000,000", out.iloc[0]["salary_text"])
        self.assertTrue(pd.isna(out.iloc[1]["salary_text"]))
        self.assertEqual(out.iloc[0]["salary_min"], 4_000_000)

    def test_empty_input_returns_the_empty_schema(self):
        out = js.to_canonical(pd.DataFrame())
        self.assertEqual(list(out.columns), COLUMNS)
        self.assertEqual(len(out), 0)

    def test_fields_unknowable_from_the_source_stay_empty(self):
        out = js.to_canonical(_jobspy_frame())
        self.assertIsNone(out.iloc[0]["education_level"])
        self.assertIsNone(out.iloc[0]["experience_text"])


class ActiveSitesTest(unittest.TestCase):
    def test_active_sites_are_a_subset_of_the_known_sites(self):
        """A site that works must be one JobSpy actually exposes."""
        self.assertTrue(set(js.ACTIVE_SITES).issubset(set(js.ALL_SITES)))

    def test_colombia_unviable_sites_are_not_active(self):
        """Probe 2026-10-05: these fail or return non-Colombian rows."""
        for site in ("glassdoor", "google", "zip_recruiter", "naukri", "bdjobs"):
            self.assertNotIn(site, js.ACTIVE_SITES, f"{site} must not be active")


if __name__ == "__main__":
    unittest.main()
