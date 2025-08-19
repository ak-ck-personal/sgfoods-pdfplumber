## Extracting tables

`pdfplumber`'s approach to table detection borrows heavily from [Anssi Nurminen's master's thesis](https://trepo.tuni.fi/bitstream/handle/123456789/21520/Nurminen.pdf?sequence=3), and is inspired by [Tabula](https://github.com/tabulapdf/tabula-extractor/issues/16). It works like this:

1. For any given PDF page, find the lines that are (a) explicitly defined and/or (b) implied by the alignment of words on the page.
2. Merge overlapping, or nearly-overlapping, lines.
3. Find the intersections of all those lines.
4. Find the most granular set of rectangles (i.e., cells) that use these intersections as their vertices.
5. Group contiguous cells into tables.

### Table-extraction methods

`pdfplumber.Page` objects can call the following table methods:

| Method                                  | Description                                                                                                                                                                                                                                  |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.find_tables(table_settings={})`       | Returns a list of `Table` objects. The `Table` object provides access to the `.cells`, `.rows`, `.columns`, and `.bbox` properties, as well as the `.extract(x_tolerance=3, y_tolerance=3)` method.                                          |
| `.find_table(table_settings={})`        | Similar to `.find_tables(...)`, but returns the _largest_ table on the page, as a `Table` object. If multiple tables have the same size — as measured by the number of cells — this method returns the table closest to the top of the page. |
| `.extract_tables(table_settings={})`    | Returns the text extracted from _all_ tables found on the page, represented as a list of lists of lists, with the structure `table -> row -> cell`.                                                                                          |
| `.extract_table(table_settings={})`     | Returns the text extracted from the _largest_ table on the page (see `.find_table(...)` above), represented as a list of lists, with the structure `row -> cell`.                                                                            |
| `.debug_tablefinder(table_settings={})` | Returns an instance of the `TableFinder` class, with access to the `.edges`, `.intersections`, `.cells`, and `.tables` properties.                                                                                                           |

For example:

```python
pdf = pdfplumber.open("path/to/my.pdf")
page = pdf.pages[0]
page.extract_table()
```

[Click here for a more detailed example.](examples/notebooks/extract-table-ca-warn-report.ipynb)

### Table-extraction settings

By default, `extract_tables` uses the page's vertical and horizontal lines (or rectangle edges) as cell-separators. But the method is highly customizable via the `table_settings` argument. The possible settings, and their defaults:

```python
{
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "explicit_vertical_lines": [],
    "explicit_horizontal_lines": [],
    "snap_tolerance": 3,
    "snap_x_tolerance": 3,
    "snap_y_tolerance": 3,
    "join_tolerance": 3,
    "join_x_tolerance": 3,
    "join_y_tolerance": 3,
    "edge_min_length": 3,
    "min_words_vertical": 3,
    "min_words_horizontal": 1,
    "intersection_tolerance": 3,
    "intersection_x_tolerance": 3,
    "intersection_y_tolerance": 3,
    "text_tolerance": 3,
    "text_x_tolerance": 3,
    "text_y_tolerance": 3,
    "text_*": …, # See below
}
```

| Setting                                                                                | Description                                                                                                                                                                                                                                                                                  |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"vertical_strategy"`                                                                  | Either `"lines"`, `"lines_strict"`, `"text"`, or `"explicit"`. See explanation below.                                                                                                                                                                                                        |
| `"horizontal_strategy"`                                                                | Either `"lines"`, `"lines_strict"`, `"text"`, or `"explicit"`. See explanation below.                                                                                                                                                                                                        |
| `"explicit_vertical_lines"`                                                            | A list of vertical lines that explicitly demarcate cells in the table. Can be used in combination with any of the strategies above. Items in the list should be either numbers — indicating the `x` coordinate of a line the full height of the page — or `line`/`rect`/`curve` objects.     |
| `"explicit_horizontal_lines"`                                                          | A list of horizontal lines that explicitly demarcate cells in the table. Can be used in combination with any of the strategies above. Items in the list should be either numbers — indicating the `y` coordinate of a line the full height of the page — or `line`/`rect`/`curve` objects.   |
| `"snap_tolerance"`, `"snap_x_tolerance"`, `"snap_y_tolerance"`                         | Parallel lines within `snap_tolerance` points will be "snapped" to the same horizontal or vertical position.                                                                                                                                                                                 |
| `"join_tolerance"`, `"join_x_tolerance"`, `"join_y_tolerance"`                         | Line segments on the same infinite line, and whose ends are within `join_tolerance` of one another, will be "joined" into a single line segment.                                                                                                                                             |
| `"edge_min_length"`                                                                    | Edges shorter than `edge_min_length` will be discarded before attempting to reconstruct the table.                                                                                                                                                                                           |
| `"min_words_vertical"`                                                                 | When using `"vertical_strategy": "text"`, at least `min_words_vertical` words must share the same alignment.                                                                                                                                                                                 |
| `"min_words_horizontal"`                                                               | When using `"horizontal_strategy": "text"`, at least `min_words_horizontal` words must share the same alignment.                                                                                                                                                                             |
| `"intersection_tolerance"`, `"intersection_x_tolerance"`, `"intersection_y_tolerance"` | When combining edges into cells, orthogonal edges must be within `intersection_tolerance` points to be considered intersecting.                                                                                                                                                              |
| `"text_*"`                                                                             | All settings prefixed with `text_` are then used when extracting text from each discovered table. All possible arguments to `Page.extract_text(...)` are also valid here.                                                                                                                    |
| `"text_x_tolerance"`, `"text_y_tolerance"`                                             | These `text_`-prefixed settings _also_ apply to the table-identification algorithm when the `text` strategy is used. I.e., when that algorithm searches for words, it will expect the individual letters in each word to be no more than `text_x_tolerance`/`text_y_tolerance` points apart. |

### Table-extraction strategies

Both `vertical_strategy` and `horizontal_strategy` accept the following options:

| Strategy         | Description                                                                                                                                                                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"lines"`        | Use the page's graphical lines — including the sides of rectangle objects — as the borders of potential table-cells.                                                                                                                              |
| `"lines_strict"` | Use the page's graphical lines — but _not_ the sides of rectangle objects — as the borders of potential table-cells.                                                                                                                              |
| `"text"`         | For `vertical_strategy`: Deduce the (imaginary) lines that connect the left, right, or center of words on the page, and use those lines as the borders of potential table-cells. For `horizontal_strategy`, the same but using the tops of words. |
| `"explicit"`     | Only use the lines explicitly defined in `explicit_vertical_lines` / `explicit_horizontal_lines`.                                                                                                                                                 |

### Notes

- Often it's helpful to crop a page — `Page.crop(bounding_box)` — before trying to extract the table.

- Table extraction for `pdfplumber` was radically redesigned for `v0.5.0`, and introduced breaking changes.
