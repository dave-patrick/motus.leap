with open("server.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "/api/playlists/videos" in line:
        print(f"Line {idx+1}: {line.strip()}")
        # print 50 lines of context
        for j in range(idx, min(len(lines), idx + 100)):
            print(f"  {j+1}: {lines[j].rstrip()}")
        break
