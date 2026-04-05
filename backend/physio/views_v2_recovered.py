import os, glob, time

appdata = os.environ.get('APPDATA')
history_path = os.path.join(appdata, 'Code', 'User', 'History')
matches = []

now = time.time()
print('Searching...')
count = 0
for root, dirs, files in os.walk(history_path):
    for f in files:
        path = os.path.join(root, f)
        count += 1
        if now - os.path.getmtime(path) > 86400 * 2: # Only last 2 days
            continue
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                content = fp.read()
                if 'class ExplainWithAIView(views.APIView):' in content and 'PhysioRiskSimulationRun.objects.create' in content:
                    matches.append((os.path.getmtime(path), path))
        except Exception:
            pass
            
print('Searched', count, 'files')
matches.sort(reverse=True)
if matches:
    print('Latest match:', matches[0][1])
    with open('backend/physio/views_v2_recovered.py', 'w', encoding='utf-8') as out:
        with open(matches[0][1], 'r', encoding='utf-8') as src:
            out.write(src.read())
    print('Recovered to backend/physio/views_v2_recovered.py')
else:
    print('No match found')
