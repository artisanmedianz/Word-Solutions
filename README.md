# Word Solutions: historical Wordle answers

This package produces a single static JSON file for the iOS app: `data/wordle-solutions.json`. It covers **published past puzzles only**. `asOfDate` tells the app how current the file is. Each unique answer has `word`, `timesUsed`, `lastUsed` (ISO date), and all `puzzleNumbers` so repeats remain auditable. Puzzle #0 was 19 June 2021.

## Setup

1. Create a GitHub repository and copy the *contents* of this folder into its root. Set Actions workflow permissions to **Read and write permissions** under Settings → Actions → General.
2. Run **Actions → Refresh Wordle history → Run workflow** once. The first run backfills historical dates and can take several minutes. A failed run publishes no new JSON; read its log and retry. Subsequent runs check gaps and the last seven days.
3. Set **Settings → Pages → Build and deployment → Deploy from a branch**, branch `main`, folder `/ (root)`. Your app URL will be `https://YOUR-USERNAME.github.io/YOUR-REPO/data/wordle-solutions.json`. Alternatively host that JSON file at any stable HTTPS URL. If your repository is private, GitHub Pages availability and visibility depend on your plan and settings.
4. The workflow runs daily at **12:30 UTC**, after the prior UTC date has ended. GitHub scheduled jobs can run late; the app should keep its last valid copy and show the `asOfDate` when freshness matters. Run the workflow manually to catch up after downtime.

The script uses the NYT date-specific puzzle response to fill missing dates and recheck recent entries. It optionally seeds from [johnfoland/nyt-wordle-played](https://github.com/johnfoland/nyt-wordle-played), a CC0 historical archive. This is an independent tool and is not affiliated with or endorsed by The New York Times. The NYT endpoint is not a documented public developer API; it may change or block automated requests. Check its current usage terms before production deployment. If access fails, the workflow fails visibly and retains the last good file.

## App integration

Decode the file and cache it locally. Calculate `daysSinceLastUsed` at display time using the device's local calendar date and `lastUsed`, rather than storing a number that becomes stale every midnight. For a word missing from `words`, show “Not previously used” only if the history is complete and current enough for your desired cutoff. Avoid loading today's solution from any source into the public file before that date has ended.

```swift
struct History: Decodable {
    let schemaVersion: Int
    let asOfDate: String
    let puzzleCount: Int
    let words: [PastWord]
}
struct PastWord: Decodable {
    let word: String
    let timesUsed: Int
    let lastUsed: String
    let puzzleNumbers: [Int]
}

func daysSinceLastUsed(_ value: String, calendar: Calendar = .current) -> Int? {
    let format = DateFormatter()
    format.calendar = Calendar(identifier: .gregorian)
    format.locale = Locale(identifier: "en_US_POSIX")
    format.timeZone = TimeZone(secondsFromGMT: 0)
    format.dateFormat = "yyyy-MM-dd"
    guard let date = format.date(from: value) else { return nil }
    // Parse the ISO components as a date in the user's calendar to avoid UTC offsets.
    let parts = Calendar(identifier: .gregorian).dateComponents(in: TimeZone(secondsFromGMT: 0)!, from: date)
    guard let local = calendar.date(from: DateComponents(year: parts.year, month: parts.month, day: parts.day)) else { return nil }
    return calendar.dateComponents([.day], from: calendar.startOfDay(for: local), to: calendar.startOfDay(for: Date())).day
}
```

The JSON is small enough to fetch as one resource. Refresh on launch when network is available, and retain the previous valid download on failure. Require `schemaVersion == 1`; reject an unexpectedly older `asOfDate` or a smaller `puzzleCount` than your cached copy.

## Local use

`python3 update.py` builds online. `python3 update.py --no-network --as-of YYYY-MM-DD` validates and rebuilds a saved complete history offline. Keep `data/history.json` in version control: it is the audit trail and protects against source outages.
