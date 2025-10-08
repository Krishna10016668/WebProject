
field_info = {'name': field_name, 'label': field_label}
            
codeword = field_type_codeword
field_info['type'] = codeword

# 5. Logic for 'select' (dropdown) fields
if codeword == 'select':
# Data for options starts from Row 3 (index 2)
# Use unique values in the rest of the column for options
            field_options = column_data.iloc[2:].unique().tolist()
            field_info['options'] = field_options
            