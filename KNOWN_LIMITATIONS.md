# Known Limitations

Deliberate scope limits of the normalization engine. Consumers of the produced
parquet artifacts should account for these.

## `source_checksum` is caller-attested, never verified

The checksum supplied at suggest time is recorded into `manifest.json` as-is;
the engine never re-reads the source to verify it. Callers own checksum
correctness.

## Excel serial dates parse only between 20000 and 59999

Serial-number dates are recognized only within 20000–59999 days from the
1899-12-30 epoch (1954-10-03 to 2064-04-07); a bare year like `2023` is
therefore never read as a serial, and serials outside the window do not parse.
Two-digit years (`01/02/98`) are likewise rejected: the century would be a
guess.

## Scientific / exponent notation is not a valid decimal input

`1.5e10`, `1.23E5`, `4.56e-3` are rejected as `INVALID_DECIMAL` (nulled, raw
text preserved) rather than converted: the stored decimal type is sized from a
value's literal digits, which exponent notation does not express. Expand such
values before submission, or type the column `string`.

## JSON sources must be arrays of flat, consistent objects

A JSON file whose objects do not share a consistent key set is rejected at
suggest time.

## One table per run

One `SourceRef`, one selected Excel worksheet, one ingested table. No
multi-sheet or multi-workbook alignment.
