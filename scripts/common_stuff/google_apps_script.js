/**
 * Universal Multi-Agent Google Apps Script Remote Logger
 * ------------------------------------------------------
 * Supports multi-sheet routing in the same Google Spreadsheet:
 * 1. Sheet "Resume Logs": Captures Resume Tailoring events (Result Time, Status, Company, Local Machine Filepath).
 * 2. Sheet "Job Applications": Captures Job Application events (Timestamp, Job Title, Company, Portal, Status, Questions Answered).
 *
 * Setup Instructions:
 * 1. Open your existing Google Spreadsheet (https://sheets.google.com).
 * 2. Click "Extensions" -> "Apps Script".
 * 3. Replace the existing Code.gs code with this file.
 * 4. Click "Deploy" -> "Manage deployments" -> edit/redeploy as "New version".
 * 5. Set GOOGLE_SHEETS_WEBHOOK_URL in appsettings.json or .env.
 */

function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var data = {};
    if (e && e.postData && e.postData.contents) {
      data = JSON.parse(e.postData.contents);
    }
    
    // Check if event is for Resume Tailoring / Resume Logs
    if (data.log_type === "resume_tailoring" || data.action === "TAILOR_RESUME") {
      var resumeSheet = ss.getSheetByName("Resume Logs");
      if (!resumeSheet) {
        resumeSheet = ss.insertSheet("Resume Logs");
      }
      
      // Auto-create bold headers if sheet is empty
      if (resumeSheet.getLastRow() === 0) {
        resumeSheet.appendRow(["Result Time", "Status", "Company", "Local Machine Filepath"]);
        resumeSheet.getRange(1, 1, 1, 4).setFontWeight("bold");
      }
      
      var resultTime = data.result_time || data.timestamp || new Date().toISOString();
      var status = data.status || "UNKNOWN";
      var company = data.company || "Unknown Company";
      var localFilepath = data.local_filepath || data.pdf_path || "N/A";
      
      resumeSheet.appendRow([resultTime, status, company, localFilepath]);
      
      return ContentService
        .createTextOutput(JSON.stringify({ "status": "success", "sheet": "Resume Logs", "message": "Resume log appended." }))
        .setMimeType(ContentService.MimeType.JSON);
    } 
    else {
      // Default: Job Application logs
      var appSheet = ss.getSheetByName("Job Applications");
      if (!appSheet) {
        appSheet = ss.getActiveSheet();
      }
      
      if (appSheet.getLastRow() === 0) {
        appSheet.appendRow(["Timestamp", "Job Title", "Company", "Portal", "Status", "Questions Answered"]);
        appSheet.getRange(1, 1, 1, 6).setFontWeight("bold");
      }
      
      var timestamp = data.timestamp || new Date().toISOString();
      var jobTitle = data.job_title || "Unknown Job";
      var company = data.company || data.company_name || "Unknown Company";
      var portal = data.portal || "Unknown Portal";
      var status = data.status || "UNKNOWN";
      var questionsAnswered = data.questions_answered !== undefined ? data.questions_answered : 0;
      
      appSheet.appendRow([timestamp, jobTitle, company, portal, status, questionsAnswered]);
      
      return ContentService
        .createTextOutput(JSON.stringify({ "status": "success", "sheet": "Job Applications", "message": "Application log appended." }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ "status": "error", "message": err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput("Universal Multi-Agent Google Sheets Logger is active!");
}
