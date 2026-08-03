"""Typing phase — infers a ColumnConfig for each column of a parsed source.

The model is shown each column's name and a sample of its values rather than raw
file text: the columns are already separated by the time this runs, so nothing is
spent re-deriving them. It echoes each name back, which is what pairs its answer
to the right column.
"""

from __future__ import annotations

import json

from shared.db.column_index import build_position_to_name
from shared.models.column import ColumnConfig, DateColumnConfig, DateTimeColumnConfig
from shared.parsing.temporal_matching import infer_date_day_first, infer_datetime_day_first

from suggestion.ai.formats import pair_typings, typing_answer_for
from suggestion.ai.providers import FileInferenceProvider, get_inference_provider
from suggestion.constants import TYPING_VALUES_PER_COLUMN
from suggestion.display import read_sample_values
from suggestion.source import SourceReading

_TYPING_PROMPT = """\
You are given the columns of one tabular source. Each carries its name and a
sample of the values found in it.

For every column, report its name exactly as given, its normalized type config,
and your confidence (0.0-1.0) in that typing. Return one entry per column.

Type-family disambiguation — the schema names each option; use these rules to
choose between the ones that look alike:
- Numeric: integer has no fractional part and no symbols. decimal has a
  fractional part but no currency or percent symbol. currency carries a
  currency symbol or code ($, €, £, USD, ...). percentage carries a % sign.
  signed carries an explicit sign notation (CR/DR words, parentheses-as-negative,
  a trailing +/-) but no currency symbol. accounting carries a currency symbol
  together with sign notation.
- Temporal: date is a calendar date with no time-of-day component. datetime
  carries both a date and a time-of-day. time is a time-of-day with no date
  component. A whole-number column clustered around 40000-50000, named like
  serial/posting/period, is a spreadsheet serial date — not an integer.
- identifier marks values that are row keys or codes to pass through unchanged
  (IDs, UUIDs, order/reference numbers) — never parsed or normalized as free
  text. Use identifier_kind "primary" only for the column that uniquely keys
  the row.
- boolean is only for a column whose entire observed value set is a
  true/false-style pair (yes/no, true/false, 1/0, y/n) — not a numeric or
  categorical column that merely happens to show two values in this sample.
{extended_guide}
Default to string whenever the sample does not clearly support a narrower
type; do not guess from the column name alone.

Columns:
{columns}
"""

_EXTENDED_TYPE_GUIDE = """\
- categorical marks a closed, repeating set of labels (order status, region,
  channel) — pick it only when the sample's distinct values are few relative
  to the row count and read as named categories, not free text. List each
  canonical value once.
- country_code, currency_code, and language_code apply only when values are
  actual ISO codes (alpha-2/alpha-3 country, ISO 4217 currency, ISO 639
  language) — not free-text country, currency, or language names.
- email, url, ip_address, and phone apply only when the sampled values
  consistently match that structured format.
"""


def type_columns(
    reading: SourceReading,
    extended_type_detection: bool,
    provider: FileInferenceProvider | None = None,
) -> tuple[dict[str, ColumnConfig], dict[str, float]]:
    """Type every column of a parsed source, keyed by position.

    ``provider`` is injectable for tests; production reads it from settings.
    """
    position_to_name = build_position_to_name(reading.column_names)
    values = read_sample_values(
        reading.inference_rows,
        position_to_name,
        limit=TYPING_VALUES_PER_COLUMN,
    )
    prompt = _TYPING_PROMPT.format(
        extended_guide=_EXTENDED_TYPE_GUIDE if extended_type_detection else "",
        columns=json.dumps(
            [
                {"name": name, "values": values[pos]}
                for pos, name in position_to_name.items()
            ],
            ensure_ascii=False,
            indent=2,
        ),
    )
    provider = provider or get_inference_provider()
    answer = provider.infer_schema(prompt, typing_answer_for(extended_type_detection))
    column_config, confidence = pair_typings(reading.column_names, answer.columns)
    return (
        {pos: _with_day_order(config, values[pos]) for pos, config in column_config.items()},
        confidence,
    )


def _with_day_order(config: ColumnConfig, values: list[str]) -> ColumnConfig:
    """Return the config with any day/month order read off the column's own values.

    The order is decidable from the values, so it is never asked of the model:
    a required field on one branch of the config union distorts which branch the
    model picks at all.
    """
    if isinstance(config, DateColumnConfig):
        return config.model_copy(update={"day_first": infer_date_day_first(values)[0]})
    if isinstance(config, DateTimeColumnConfig):
        return config.model_copy(update={"day_first": infer_datetime_day_first(values)[0]})
    return config
