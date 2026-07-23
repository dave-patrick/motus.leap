import pathlib

# Fix JavaScript syntax error in ux-enhancements.js
p = pathlib.Path('tube-manager/web/static/ux-enhancements.js')
t = p.read_text()

# Fix the double }} before else - version parameter doesn't matter for this fix
t = t.replace('}} else if (taskName.includes(\'Scan\') || taskName.includes(\'Duplicate\') || taskName.includes(\'Misplaced\')) {', '} else if (taskName.includes(\'Scan\') || taskName.includes(\'Duplicate\') || taskName.includes(\'Misplaced\')) {')

p.write_text(t)
print("✅ Fixed JavaScript syntax error properly")
