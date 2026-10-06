import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import pandas as pd
import requests
from requests.exceptions import SSLError

from pipeline.sources import spe


class ParseSalaryTest(unittest.TestCase):
    def test_range_becomes_numeric_pair(self):
        self.assertEqual(spe._parse_salary("$1.500.001 - $2.000.000"), (1_500_001, 2_000_000))

    def test_above_max_is_open_ended(self):
        self.assertEqual(spe._parse_salary("Mayor de $15.000.001"), (15_000_001, None))

    def test_non_numeric_bands_give_nothing(self):
        for band in ("A Convenir", "Menos del salario mínimo", None, 42):
            self.assertEqual(spe._parse_salary(band), (None, None))


class ToCanonicalTest(unittest.TestCase):
    def _csv(self, tmp: str) -> Path:
        path = Path(tmp) / "export.csv"
        path.write_text(
            "CODIGO_VACANTE,TITULO_VACANTE,DESCRIPCION_VACANTE,NIVEL_ESTUDIOS,"
            "RANGO_SALARIAL,NOMBRE_PRESTADOR,DEPARTAMENTO,MUNICIPIO,TIPO_CONTRATO,"
            "URL_DETALLE_VACANTE,FECHA_PUBLICACION,TELETRABAJO,MESES_EXPERIENCIA_CARGO\n"
            "123,Analista,\"Se requiere experiencia\",Universitario,"
            "\"$2.000.001 - $3.000.000\",Empresa SA,Cundinamarca,Bogotá,Término fijo,"
            "https://ejemplo.co/123,2026-09-01,1,24\n",
            encoding="utf-8-sig",
        )
        return path

    def test_maps_raw_columns_to_the_canonical_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = spe.to_canonical(self._csv(tmp), captured_at="2026-10-05 10:00:00")

        from pipeline.schema import COLUMNS

        self.assertEqual(list(frame.columns), COLUMNS)
        row = frame.iloc[0]
        self.assertEqual(row["vacancy_id"], "spe-123")
        self.assertEqual(row["source"], "spe")
        self.assertEqual(row["salary_min"], 2_000_001.0)
        self.assertEqual(row["work_modality"], "Teletrabajo")
        self.assertEqual(row["experience_text"], "24 meses")
        self.assertEqual(row["captured_at"], "2026-10-05 10:00:00")


class VerifySslTest(unittest.TestCase):
    """The SPE CA chain is incomplete: validation always fails.

    Every request used to repeat the verified-then-failed handshake before
    retrying unverified (100-132 warnings per run). Now the first SSLError
    decides for the rest of the run.
    """

    def setUp(self):
        self.previous = spe._VERIFY_SSL
        spe._VERIFY_SSL = True

    def tearDown(self):
        spe._VERIFY_SSL = self.previous

    def _mock_spe(self, fails_when_verifying):
        modes = []

        def _req(method, url, **kw):
            verify = kw.get("verify", True)
            modes.append(verify)
            if verify and fails_when_verifying:
                raise SSLError("incomplete CA chain")
            return requests.Response()

        return mock.patch.object(spe.requests, "request", side_effect=_req), modes

    def test_first_sslerror_disables_verification_for_the_run(self):
        patcher, modes = self._mock_spe(fails_when_verifying=True)
        with patcher:
            for _ in range(3):
                spe._request("GET", "https://ejemplo.invalid/x")

        # 3 requests: only the first pays the verified attempt.
        self.assertEqual(modes, [True, False, False, False])

    def test_the_warning_is_emitted_exactly_once(self):
        patcher, _ = self._mock_spe(fails_when_verifying=True)
        with patcher, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for _ in range(4):
                spe._request("GET", "https://ejemplo.invalid/x")

        tls_warnings = [w for w in caught if "TLS" in str(w.message)]
        self.assertEqual(len(tls_warnings), 1, f"expected 1 warning, got {len(tls_warnings)}")

    def test_when_tls_works_verification_is_never_disabled(self):
        patcher, modes = self._mock_spe(fails_when_verifying=False)
        with patcher:
            for _ in range(3):
                spe._request("GET", "https://ejemplo.invalid/x")

        self.assertEqual(modes, [True, True, True])
        self.assertTrue(spe._VERIFY_SSL, "a valid chain must not disable verification")

    def test_flag_resets_between_runs(self):
        """The flag is per-process: a fixed chain is retried next run."""
        patcher, _ = self._mock_spe(fails_when_verifying=True)
        with patcher:
            spe._request("GET", "https://ejemplo.invalid/x")
        self.assertFalse(spe._VERIFY_SSL)

        spe._VERIFY_SSL = True  # new process
        patcher2, modes = self._mock_spe(fails_when_verifying=False)
        with patcher2:
            spe._request("GET", "https://ejemplo.invalid/x")
        self.assertEqual(modes, [True])


if __name__ == "__main__":
    unittest.main()
