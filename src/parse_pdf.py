import os
import sys, pathlib, pymupdf
import gspread
from gspread_formatting import *
from referral import Referral

# Convert pdf text into txt format
def pdf_to_txt(fname):
    with pymupdf.open(fname) as doc:
        text = chr(12).join([page.get_text() for page in doc])
    pathlib.Path(fname + ".txt").write_bytes(text.encode())

# Find what row to write to
def find_last_empty_row(sheet):
    all_values = sheet.get_all_values()
    # If previous row is empty but this one is not, that's our guy
    for row_num in range(len(all_values) - 1, 0, -1):
        if all_values[row_num][0] == "":
            return row_num + 1

    return 0

# Write referral info to sheet
def write(sheet, row_number, ref):
    # Prepare a batch update from Cell objects
    cells = ref.to_array(row_number)
    cell_updates = []
    for cell in cells:
        cell_updates.append({
            "range": gspread.utils.rowcol_to_a1(cell.row, cell.col),
            "values": [[cell.value]]
        })

    # Batch update the sheet
    data = [{"range": update["range"], "values": update["values"]} for update in cell_updates]
    # sheet.batch_update(data, value_input_options = 'RAW')
    sheet.batch_update(data, value_input_option='RAW')

def main():
    # Open intake spreadsheet
    gc = gspread.oauth()
    sh = gc.open("Kaiser Referrals 2025").sheet1
    fname = sys.argv[1]
    pdf_to_txt(fname)

    with open(fname + ".txt", 'r') as file:
        content = file.readlines()    
        ref = Referral.from_file(content)
        # Log
        ref.log()
        # Update spreadsheet
        last_empty_row = find_last_empty_row(sh)
        if last_empty_row == 0:
            raise ValueError("Unable to find writeable row")
        write(sh, last_empty_row, ref)
    
    os.remove(f"{fname}.txt")

#TODO Generalize for denials as well

if __name__ == "__main__":
    main()