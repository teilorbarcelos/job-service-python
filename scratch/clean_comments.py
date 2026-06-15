import os
import re

def remove_comments(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove docstrings (triple quotes)
    content = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\')', '', content, flags=re.DOTALL)
    
    # Remove single line comments
    # Special care not to remove # inside strings (simple regex, might have edge cases)
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if '#' in line:
            # Simple check: if # is not inside a string
            # We look for the first # that is not preceded by an odd number of quotes
            parts = re.split(r'(\'|")', line)
            in_string = False
            quote_char = None
            clean_line = ""
            for i, part in enumerate(parts):
                if part in ['\'', '"']:
                    if not in_string:
                        in_string = True
                        quote_char = part
                    elif part == quote_char:
                        in_string = False
                        quote_char = None
                    clean_line += part
                elif '#' in part and not in_string:
                    clean_line += part.split('#')[0]
                    break
                else:
                    clean_line += part
            new_lines.append(clean_line.rstrip())
        else:
            new_lines.append(line)
            
    # Remove extra empty lines caused by deletions
    final_content = '\n'.join(new_lines)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

def clean_dir(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                remove_comments(path)

# Clean src and tests
clean_dir('src')
clean_dir('tests')
print("Comments removed successfully.")
