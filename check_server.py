import urllib.request

try:
    resp = urllib.request.urlopen('http://127.0.0.1:5000/', timeout=3)
    html = resp.read().decode('utf-8')
    print('HTML size:', len(html))
    checks = ['page-home', 'page-mapping', 'main.js', 'mapping.js', 'style.css', 'advCanvas']
    for c in checks:
        status = 'OK' if c in html else 'MISSING'
        print(status + ': ' + c)
except Exception as e:
    print('FAILED: ' + str(e))
