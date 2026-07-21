import { formatSelectionAsMarkdown, type IMarkdownSelectionCell } from './markdownTable';

function assertEqual(actual: any, expected: any, message: string) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

const selection: IMarkdownSelectionCell[][] = [
  [
    { row: 2, col: 2, field: 'name', value: 'Grace | Hopper' },
    { row: 2, col: 1, field: 'id', dataValue: 2 },
  ],
  [
    { row: 1, col: 2, field: 'name', value: 'Ada\nLovelace' },
    { row: 1, col: 1, field: 'id', value: 1 },
  ],
];

assertEqual(
  formatSelectionAsMarkdown(selection, (cell) => ({ id: 'User ID', name: 'Name | bio' })[String(cell.field)]),
  [
    '| User ID | Name \\| bio |',
    '| --- | --- |',
    '| 1 | Ada<br>Lovelace |',
    '| 2 | Grace \\| Hopper |',
  ].join('\n'),
  'formats selected cells by row and column with Markdown escaping',
);

assertEqual(
  formatSelectionAsMarkdown([
    [{ row: 3, col: 1, field: 'id', value: null }],
    [{ row: 4, col: 2, field: 'note', value: '' }],
  ]),
  ['| id | note |', '| --- | --- |', '| NULL |  |', '|  |  |'].join('\n'),
  'preserves sparse selections and distinguishes NULL from an empty string',
);

assertEqual(
  formatSelectionAsMarkdown([[{ row: 0, col: 1, field: 'id', value: 'id' }]]),
  null,
  'ignores header-only selections',
);

console.log('copy selection as Markdown tests passed');
