from pathlib import Path

app_file = Path('dashboard/app.py')
content = app_file.read_text(encoding='utf-8')

old = 'app.run(debug=True, port=5000, host="0.0.0.0")'
new = '''port = int(__import__("os").environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)'''

if old in content:
    content = content.replace(old, new)
    app_file.write_text(content, encoding='utf-8')
    print('dashboard/app.py updated')
else:
    print('Manual update needed in dashboard/app.py')
    print('Find the last app.run() line and replace with:')
    print('  port = int(os.environ.get("PORT", 8080))')
    print('  app.run(debug=False, host="0.0.0.0", port=port)')
