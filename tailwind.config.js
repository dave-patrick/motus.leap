module.exports = {
  content: [
    './web/**/*.html',
    './web/static/**/*.js',
    './app.py'
  ],
  safelist: [
    { pattern: /(bg|text|border)-(red|green|yellow|amber|blue|gray)-(100|200|300|400|500|600|700|800|900|950)/ },
    { pattern: /(translate|scale|opacity)-.*/ }
  ],
  theme: { extend: {} },
  plugins: []
};
