/**
 * Google Apps Script Web App Snippet for Application Logging
 * -----------------------------------------------------------
 * Setup Instructions:
 * 1. Open Google Sheets (https://sheets.google.com) and create/open a spreadsheet.
 * 2. Click on "Extensions" -> "Apps Script".
 * 3. Delete any code in Code.gs and paste the contents of this file.
 * 4. Click "Deploy" -> "New deployment".
 * 5. Select type "Web app" (click gear icon next to Select type).
 * 6. Set Description to "Job Applications Logger".
 * 7. Set "Execute as": "Me".
 * 8. Set "Who has access": "Anyone".
 * 9. Click "Deploy", complete permission authorization.
 * 10. Copy the Web App URL and set in your .env:
 *     GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // Auto-create bold headers if sheet is empty
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Timestamp", "Job Title", "Company", "Portal", "Status", "Questions Answered"]);
      sheet.getRange(1, 1, 1, 6).setFontWeight("bold");
    }
    
    var data = {};
    if (e && e.postData && e.postData.contents) {
      data = JSON.parse(e.postData.contents);
    }
    
    var timestamp = data.timestamp || new Date().toISOString();
    var jobTitle = data.job_title || "Unknown Job";
    var company = data.company || data.company_name || "Unknown Company";
    var portal = data.portal || "Unknown Portal";
    var status = data.status || "UNKNOWN";
    var questionsAnswered = data.questions_answered !== undefined ? data.questions_answered : 0;
    
    sheet.appendRow([timestamp, jobTitle, company, portal, status, questionsAnswered]);
    
    return ContentService
      .createTextOutput(JSON.stringify({ "status": "success", "message": "Row logged successfully" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ "status": "error", "message": err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput("Google Sheets Application Remote Logger Webhook is active!");
}
