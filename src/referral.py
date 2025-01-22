from enum import Enum
import itertools
import os
import re
from gspread.cell import Cell

class Referral(object):
    def __init__(self, ref, recv, urgency, status, name, mrn, dob, codes):
        # Find policy then adapt how things are fetched
        self.current_location = Referral.find_origin()
        self.ref_number = ref
        self.recv_date = recv
        self.urgency = urgency
        self.status = status
        self.name = name
        self.mrn = mrn
        self.dob = dob
        self.codes = codes


    # Return name of calling user as described on sheet
    def find_origin():
        name_mappings = {'jbaum': 'Justice', 'caikala':'Charles'}
        name = os.environ.get('USER', os.environ.get('USERNAME'))
        current_location = name_mappings.get(name)
        
        return current_location
    
    # Construct Referral object from content
    def from_file(content):
            auth_status = Referral.extract_auth_status(content)
            referral_number = Referral.extract_referral_num(content)
            date_received = Referral.extract_received_date(content, auth_status)
            urgency = Referral.extract_urgency(content)
            name_mrn = Referral.extract_patient_name_mrn(content)
            dob = Referral.extract_dob(content, auth_status)
            codes = Referral.extract_proc_codes(content)

            return Referral(referral_number, date_received, urgency, auth_status, name_mrn[0], name_mrn[1], dob, codes)

    # Return referral number
    def extract_referral_num(content):
        return content[0].split(' ')[2].strip()

    # Return date of receipt
    def extract_received_date(content, auth_status):
        #TODO: Make this a more general search like the DoB one
        match auth_status:
            case AuthState.AUTHORIZED:
                return content[8].strip()
            case AuthState.DENIED:
                return content[9].strip()
    
    # Returns whether 'tis urgent or not 
    def extract_urgency(content):
        status = content[51].strip()
        if status == 'Routine':
            return False
        else:
            return True

    # Return patient's name and MRN as a tuple
    def extract_patient_name_mrn(content):
        tokenized = content[1].split(' ')
        name = f"{tokenized[1]} {tokenized[0]}".replace(",", "")
        mrn = tokenized[len(tokenized) - 1].strip().replace(")","")
        if "<" in mrn:
            mrn = "NEEDS MANUAL REVIEW"
        return name,mrn

    # Return all HCPCS codes in the document
    def extract_proc_codes(content):
        pattern = r'[A-Za-z]\d{4}\n'
        codes = set()
        for lines in content:
            matches = re.findall(pattern, lines)
            codes.update(matches)
        sanitized_codes = {entries.strip() for entries in codes}
        return sanitized_codes

    # Return patient's date of birth
    #TODO: Doesn't work for ...266?
    def extract_dob(content, auth_status):
        dob = None
        match auth_status:
            case AuthState.AUTHORIZED:
                # Demo. info starts around this line and can vary based on numer of HCPCS
                # So can't just fetch a static line
                for line_number, line in enumerate(itertools.islice(content, 150, None), start=0):
                        if line_number > 0 and 'Birth: ' in previous_line:
                            dob = line.strip()
                            break
                        previous_line = line
                return dob
            case AuthState.DENIED:
                for line_number, line in enumerate(itertools.islice(content, 150, None), start = 0):
                    if "Birth:" in line:
                        dob = line
                splitdob = dob.split(":")
                dob = splitdob[1].strip()
                return dob
            case _:
                return dob
        return dob
    
    # Return auth approved or denied?
    def extract_auth_status(content):
        status = content[2].strip()
        if "Denied" in status:
            status = AuthState.DENIED
        elif "Covered Benefit" in status:
            status = AuthState.AUTHORIZED
        elif "No Approval Needed" in status:
            status = AuthState.REFERRAL
        elif "Order Canceled" in status:
            status = AuthState.CANCELED
        return status
    
    # Return what dept the referral is for
    #TODO
    def find_department(content):
        pass
    
    # Return what policy option should be in the dropdown
    #TODO
    def find_policy(content):
        pass

    # Return all properties as an array of Cell objects
    def to_array(self, start_row):
        column_mapping = {
            'current_location': 1,     # Column A
            'ref_number': 2,  # Column B
            'recv_date': 3,   # Column C
            'urgency': 4,      # Column D
            'status': 6,      # Column F
            'name': 8,        # Column H 
            'mrn': 9,         # Column I
            'dob': 10,        # Column J
            'codes': 11       # Column K-M
        }
        
        # Prepare Cell objects
        cells = []
        for attribute, col in column_mapping.items():
            value = getattr(self, attribute)

            # Normalize the status value
            if attribute == 'status':
                value = self.normalize_status()

            if isinstance(value, set):
                value = list(value)

            if attribute == 'codes':
                # This is an awful way to do it but whatever
                if len(value) > 3:
                    value = [value[0], value[1], True]
                elif len(value) == 3:
                    value[2] = True

                for i,val in enumerate(value):
                    cells.append(Cell(row=start_row, col=col+i, value=val))
            else:
                cells.append(Cell(row=start_row, col=col, value=value))

        return cells
    
    def normalize_status(self):
        status_mapping = {
            AuthState.AUTHORIZED: 'Authorized',
            AuthState.REFERRAL: 'Referral only',
            AuthState.DENIED: 'Denied',
            AuthState.CANCELED: 'Canceled'
        }

        dropdown_options = {'Authorized', 'Denied', 'Referral only', 'Canceled'}

        normalized_value = status_mapping.get(self.status, self.status)
        if normalized_value not in dropdown_options:
            raise ValueError(f"Invalid status: '{self.status}' (mapped to '{normalized_value}'). Must match one of {dropdown_options}.")
        return normalized_value
    
    def log(self):
        print(f"Caller: {self.current_location}")
        print(f"Referral: {self.ref_number}")
        print(f"Date received: {self.recv_date}")
        if self.urgency == 'Routine':
            print("Urgency: Routine")
        else:
            print("Urgency: Urgent")
        print(f"Auth. Status: {self.status}")
        print(f"Patient name: {self.name}")
        print(f"Patient MRN: {self.mrn}")
        print(f"Patient Date of Birth: {self.dob}")
        print(f"HCPCS code(s): {self.codes}")

class AuthState(Enum):
    AUTHORIZED = 1,
    DENIED = 2,
    REFERRAL = 3,
    CANCELED = 4