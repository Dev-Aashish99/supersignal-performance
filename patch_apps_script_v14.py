"""
Patch your V13 Apps Script -> V14 (forwards every TEST-channel message to the tracker).
  1. In the Apps Script editor, select all, copy, save as  trade_journal_v13.gs
  2. python patch_apps_script_v14.py trade_journal_v13.gs trade_journal_v14.gs
  3. Paste trade_journal_v14.gs back into the editor, save.
  4. Run menu: Telegram > Setup Performance Tracker link  (enter URL + token; stored in Script
     Properties, never in the code).
It only ADDS a forward call that runs after ALL channels have been sent, and only for the test channel. Telegram/Firestore behaviour is unchanged,
and a tracker outage can never block an alert (errors are only logged).
"""
import sys

EDITS = [
 # (anchor that must appear exactly once, replacement)
 ('  SHEET_NAME: "Trade_Journal",',
  '  TEST_CHAT_ID: "-1002940195231",   // V14: this channel is mirrored to the performance tracker\n'
  '  SHEET_NAME: "Trade_Journal",'),
 ("    .addItem('Setup / Repair Timestamp Columns', 'setupTimestampColumns')",
  "    .addItem('Setup / Repair Timestamp Columns', 'setupTimestampColumns')\n"
  "    .addItem('Setup Performance Tracker link', 'setupTrackerProps')"),
 ("  let allOk = true;",
  "  let allOk = true;\n  let testResp = null;   // V14: response from the test channel only"),
 ("    try { UrlFetchApp.fetch(url, payload); }",
  "    try {\n"
  "      const resp = UrlFetchApp.fetch(url, payload);\n"
  "      if (String(chatId) === String(CONFIG.TEST_CHAT_ID)) { testResp = resp; }\n"
  "    }"),
 ("  return allOk;",
  "  // V14: forward AFTER every channel has been sent, so the tracker can never delay the main channels\n"
  "  if (testResp) { forwardTestChannelMessage_(testResp, text); }\n"
  "  return allOk;"),
]

APPEND = r'''

// ═══════════════════════════════════════════════════════════════
// V14: PERFORMANCE TRACKER LINK
// ═══════════════════════════════════════════════════════════════

// One-time: stores the tracker URL + token in Script Properties (not in code).
function setupTrackerProps() {
  const ui = SpreadsheetApp.getUi();
  const props = PropertiesService.getScriptProperties();
  const u = ui.prompt('Tracker URL', 'e.g. https://your-tracker.up.railway.app', ui.ButtonSet.OK_CANCEL);
  if (u.getSelectedButton() !== ui.Button.OK) return;
  const t = ui.prompt('Tracker token', 'The INGEST_TOKEN you set on the tracker', ui.ButtonSet.OK_CANCEL);
  if (t.getSelectedButton() !== ui.Button.OK) return;
  props.setProperty('TRACKER_URL', u.getResponseText().trim());
  props.setProperty('TRACKER_TOKEN', t.getResponseText().trim());
  ui.alert('Saved. Every message sent to the test channel is now also sent to the tracker.');
}

// Called right after a successful send to the test channel. Never throws.
function forwardTestChannelMessage_(resp, text) {
  try {
    const props = PropertiesService.getScriptProperties();
    const base = props.getProperty('TRACKER_URL');
    const token = props.getProperty('TRACKER_TOKEN');
    if (!base || !token) { Logger.log('Tracker not configured - skipped.'); return; }
    const mid = JSON.parse(resp.getContentText()).result.message_id;
    UrlFetchApp.fetch(base.replace(/\/$/, '') + '/ingest', {
      method: 'post',
      contentType: 'application/json',
      headers: { 'X-Token': token },
      payload: JSON.stringify({ text: text, message_id: mid, date: Math.floor(Date.now() / 1000) }),
      muteHttpExceptions: true
    });
  } catch (e) {
    Logger.log('Tracker forward failed (alert already sent): ' + e);
  }
}
'''

def main(src, dst):
    s = open(src, encoding="utf-8").read()
    if "forwardTestChannelMessage_" in s:
        sys.exit("Already patched (V14).")
    for anchor, repl in EDITS:
        n = s.count(anchor)
        if n != 1:
            sys.exit(f"Anchor found {n} times (need exactly 1), aborting. Anchor:\n{anchor}")
        s = s.replace(anchor, repl)
    s = s.rstrip() + "\n" + APPEND
    open(dst, "w", encoding="utf-8").write(s)
    print("Wrote", dst)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
