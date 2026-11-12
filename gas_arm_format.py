import argparse
import re

from pygments.lexer import include, inherit
from pygments.token import Comment, Error, Name, Punctuation, String, Text, Whitespace
from pygments_arm import ArmLexer


class GnuArmLexer(ArmLexer):
  string = r'"(?:[^"\\]|\\[\s\S])*"'
  tokens = {
    "root": [
      (r"\ufeff", Text),
      (r"#[^\n\\]*(?:\\\r?\n[^\n\\]*|\\[^\r\n][^\n\\]*)*", Comment.Preproc),
      (r'"(?:[^"\\]|\\.)*":', Name.Label),
      (r"\\(?:[A-Za-z_$][\w$]*|[@+])", Name.Function, "instruction-args"),
      (r";", Punctuation),
      (r"\\\r?\n", Text),
      inherit,
    ],
    "directive-args": [
      include("gnu-args"),
      inherit,
    ],
    "instruction-args": [
      include("gnu-args"),
      inherit,
    ],
    "gnu-args": [
      include("whitespace"),
      (string, String),
      (r"'(?:![^\n]|[^'\\\n]|\\.)*'", String),
      (r"(?<![<>=])<(?![<=])(?:![^\n]|[^>\n])*>", String),
      (r"'(?:\\(?:[0-7]{1,3}|x[0-9A-Fa-f]+|.)|[^\\\n])'?", String.Char),
      (r"\\(?:[A-Za-z_$][\w$]*|[@+]|\(\))", Name.Variable),
      (r"\\\r?\n", Text),
      (r";", Punctuation, "#pop"),
      (r"[%&|~<>/?]", Punctuation),
    ],
    "whitespace": [
      (r"[ \t\r]+", Whitespace),
      (r"//[^\n]*|@[^\n]*", Comment.Single),
      (r"/\*[\s\S]*?\*/", Comment.Multiline),
    ],
  }


def format_statement(tokens, indent, directive_indent):
  while tokens and tokens[0][1].strip(" \t") == "":
    tokens = tokens[1:]
  while tokens and tokens[-1][1].strip(" \t") == "":
    tokens = tokens[:-1]
  if not tokens:
    return ""

  _, first_value = tokens[0]
  significant = [value for _, value in tokens if value.strip(" \t")]
  label_end = None
  for index, (token_type, value) in enumerate(tokens):
    if value.strip(" \t") == "":
      break
    if token_type in Name.Label or (token_type in Punctuation and value == ":"):
      label_end = index
      break
  if label_end is not None or (len(significant) > 1 and significant[1] == "="):
    prefix = ""
  elif first_value.startswith("."):
    prefix = " " * directive_indent
  else:
    prefix = " " * indent

  output = ""
  pending_space = False
  after_label = False
  parentheses = 0
  for index, (token_type, value) in enumerate(tokens):
    if token_type in Punctuation and value == "(":
      if output and (pending_space or after_label):
        output += " "
      output += value
      parentheses += 1
      pending_space = False
      after_label = False
      continue
    if parentheses:
      output += value
      if token_type in Punctuation and value == ")":
        parentheses -= 1
      continue
    if value.strip(" \t") == "":
      pending_space = True
      continue
    if token_type in Comment:
      return prefix + output.rstrip(" \t") + "  " + value
    if value == "," and token_type in Punctuation:
      output = output.rstrip(" \t") + ","
      pending_space = True
      continue
    if output and (pending_space or after_label):
      output += " "
    output += value
    pending_space = False
    after_label = index == label_end
  return prefix + output


def format_text(source, indent=2, directive_indent=0):
  bom = "\ufeff" if source.startswith("\ufeff") else ""
  source = source[len(bom) :]
  endings = re.findall(r"\r\n|\r|\n", source)
  source = source.replace("\r\n", "\n").replace("\r", "\n")
  lines = [[]]
  protected = set()
  for position, token_type, value in GnuArmLexer().get_tokens_unprocessed(source):
    if token_type in Error:
      line_number = source.count("\n", 0, position) + 1
      raise ValueError(f"Unsupported assembly token {value!r} at line {line_number}")
    parts = value.split("\n")
    for index, part in enumerate(parts):
      if (
        token_type in Comment.Preproc
        or token_type in Comment.Multiline
        or (len(parts) > 1 and token_type in String)
      ):
        protected.add(len(lines) - 1)
      if part:
        if token_type in Punctuation:
          lines[-1].extend((token_type, character) for character in part)
        else:
          lines[-1].append((token_type, part))
      if index < len(parts) - 1:
        lines.append([])

  output = []
  continued = False
  for line_number, tokens in enumerate(lines):
    original = "".join(value for _, value in tokens)
    continuation = original.endswith("\\")
    if line_number in protected or continued or continuation:
      output.append(original)
      continued = continuation
      continue
    first_token = next(
      (token_type for token_type, value in tokens if value.strip(" \t")), None
    )
    if first_token is not None and first_token in Comment:
      output.append(original)
      continue

    statements = [[]]
    parentheses = 0
    for token_type, value in tokens:
      if token_type in Punctuation and value == "(":
        parentheses += 1
      elif token_type in Punctuation and value == ")":
        parentheses -= 1
      if token_type in Punctuation and value == ";" and parentheses == 0:
        statements.append([])
      else:
        statements[-1].append((token_type, value))
    formatted = [
      format_statement(statement, indent, directive_indent) for statement in statements
    ]
    rendered = "; ".join(
      value if index == 0 else value.lstrip(" ")
      for index, value in enumerate(formatted)
    )
    output.append(rendered.rstrip(" ") if not formatted[-1] else rendered)
  return bom + "".join(
    value + (endings[index] if index < len(endings) else "")
    for index, value in enumerate(output)
  )


def main(argv=None):
  parser = argparse.ArgumentParser(description="Format GNU ARM/Thumb assembly files.")
  parser.add_argument(
    "--check",
    action="store_true",
    help="Report files needing formatting without writing them.",
  )
  parser.add_argument(
    "--indent",
    type=int,
    default=2,
    help="Instruction indentation in spaces (default: 2).",
  )
  parser.add_argument(
    "--directive-indent",
    type=int,
    default=0,
    help="Directive indentation in spaces (default: 0).",
  )
  parser.add_argument("filenames", nargs="+")
  args = parser.parse_args(argv)
  if args.indent < 0 or args.directive_indent < 0:
    parser.error("indentation must be nonnegative")

  changed = False
  for filename in args.filenames:
    with open(filename, "r", -1, "utf8") as reader:
      reader.reconfigure(newline="")
      source = reader.read()
    formatted = format_text(source, args.indent, args.directive_indent)
    if formatted != source:
      changed = True
      if args.check:
        print(filename)
      else:
        with open(filename, "w", -1, "utf8", None, "\n") as writer:
          writer.write(formatted)
  return int(args.check and changed)


if __name__ == "__main__":
  raise SystemExit(main())
