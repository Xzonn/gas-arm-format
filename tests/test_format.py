import filecmp
import os
import shutil
import subprocess
import sys

import pytest

from gas_arm_format import format_text, main


@pytest.mark.parametrize(("source", "expected"), [
  ("mov   r0,#0x20\n", "  mov r0, #0x20\n"),
  ("\tpush {r4,lr}\n", "  push {r4, lr}\n"),
  ("ldr r0,[r1,#4]!\n", "  ldr r0, [r1, #4]!\n"),
  ("  1:   b   1b\n", "1: b 1b\n"),
  ("entry:mov r0,r1\n", "entry: mov r0, r1\n"),
  (" .section  .text,\"ax\"\n", ".section .text, \"ax\"\n"),
  (".ascii  \"x,  y @ # ; //\",\"z\"\n", ".ascii \"x,  y @ # ; //\", \"z\"\n"),
  (r'.ascii "x\" ,  y", "z\\"' + "\n", r'.ascii "x\" ,  y", "z\\"' + "\n"),
  ("mov r0,#' ' @ keep  comment\n", "  mov r0, #' '  @ keep  comment\n"),
  ("mov r0,#1// keep,  comment\n", "  mov r0, #1  // keep,  comment\n"),
  (".word  (1 << 4)|2, 3 / 1\n", ".word (1 << 4)|2, 3 / 1\n"),
  ("symbol=4\n", "symbol=4\n"),
  (".ascii STR(hello,   world)\n", ".ascii STR(hello,   world)\n"),
  (".ascii STR(hello;   world)\n", ".ascii STR(hello;   world)\n"),
  ("emit <hello,   world>\n", "  emit <hello,   world>\n"),
  ("emit 'hello,   world'\n", "  emit 'hello,   world'\n"),
  (".word (1+(2  *  3)),4\n", ".word (1+(2  *  3)), 4\n"),
  ("  symbol = 4\n", "symbol = 4\n"),
  ("mov r0,#1;add  r0,r0,#2\n", "  mov r0, #1; add r0, r0, #2\n"),
  ("mov r0,#1;\n", "  mov r0, #1;\n"),
  (r"\name\()_loop:mov r0,\value" + "\n", r"\name\()_loop: mov r0, \value" + "\n"),
  ("   @ keep   indentation\n", "   @ keep   indentation\n"),
  (" \t\n\n", "\n\n"),
  ("\ufeffmov r0,r1\r\n", "\ufeff  mov r0, r1\r\n"),
  ("mov r0,r1\nmov r1,r2\r\n", "  mov r0, r1\n  mov r1, r2\r\n"),
  ("mov r0,r1\rmov r1,r2\r", "  mov r0, r1\r  mov r1, r2\r"),
  ("mov r0,r1", "  mov r0, r1"),
  ("", ""),
])
def test_format(source, expected):
  formatted = format_text(source)
  assert formatted == expected
  assert format_text(formatted) == formatted


@pytest.mark.parametrize("source", [
  " #define TEXT(x) #x\n#ifdef TEST\n#else\n#endif\n",
  "#define JOIN(a, b) \\\n   a ## b\n",
  "#define JOIN(a, b) \\\r\n   a ## b\r\n",
  "mov r0, /* first,\n   second */ r1\n",
  "mov /* keep,   spacing */ r0,r1\n",
  "    .ascii \"first\n   second\"\n",
  "mov r0, \\\n    r1\n",
])
def test_protected_source(source):
  assert format_text(source) == source


def test_indentation_options():
  assert format_text("label:\nmov r0,r1\n.word 0\n", 4, 2) == "label:\n    mov r0, r1\n  .word 0\n"


def test_unknown_token():
  with pytest.raises(ValueError, match="line 1"):
    format_text("mov r0, `\n")


def test_cli_check_and_write(tmp_path, capsys):
  filename = str(tmp_path / "source.S")
  source = "\ufeffmov r0,r1\r\nmov r2,r3\n"
  with open(filename, "w", -1, "utf8", None, "\n") as writer:
    writer.write(source)
  assert main(["--check", filename]) == 1
  assert capsys.readouterr().out.strip() == filename
  with open(filename, "r", -1, "utf8") as reader:
    reader.reconfigure(newline="")
    assert reader.read() == source
  assert main([filename]) == 0
  with open(filename, "r", -1, "utf8") as reader:
    reader.reconfigure(newline="")
    assert reader.read() == "\ufeff  mov r0, r1\r\n  mov r2, r3\n"
  assert main(["--check", filename]) == 0
  assert capsys.readouterr().out == ""


def test_cli_multiple_files(tmp_path):
  filenames = [str(tmp_path / name) for name in ("one.s", "two.S")]
  for filename in filenames:
    with open(filename, "w", -1, "utf8", None, "\n") as writer:
      writer.write("mov r0,r1\n")
  assert main(["--indent", "4", *filenames]) == 0
  for filename in filenames:
    with open(filename, "r", -1, "utf8") as reader:
      assert reader.read() == "    mov r0, r1\n"


def test_cli_invalid_indentation():
  with pytest.raises(SystemExit) as error:
    main(["--indent", "-1", "unused.S"])
  assert error.value.code == 2


@pytest.mark.parametrize(("filename", "thumb"), [
  ("arm.S", False),
  ("thumb.s", False),
  ("preprocessed.S", False),
  ("preprocessed.S", True),
])
def test_assembled_output(filename, thumb, tmp_path):
  preprocessed = filename == "preprocessed.S"
  tool = "gcc" if preprocessed else "as"
  variable = "ARM_NONE_EABI_CC" if preprocessed else "ARM_NONE_EABI_AS"
  assembler = os.environ.get(variable) or shutil.which(f"arm-none-eabi-{tool}")
  if assembler is None:
    pytest.skip(f"Set {variable} to run GNU assembler tests")
  with open(f"{os.path.dirname(__file__)}/{filename}", "r", -1, "utf8") as reader:
    source = reader.read()
  formatted = format_text(source)
  assert format_text(formatted) == formatted
  outputs = []
  for index, content in enumerate((source, formatted)):
    source_file = f"{tmp_path}/input.s"
    output_file = f"{tmp_path}/{index}.o"
    with open(source_file, "w", -1, "utf8", None, "\n") as writer:
      writer.write(content)
    command = [assembler, "-mcpu=arm946e-s"]
    if preprocessed:
      command.extend(["-x", "assembler-with-cpp", "-c"])
      if thumb:
        command.append("-DTHUMB")
    command.extend([source_file, "-o", output_file])
    subprocess.run(command, check=True)
    outputs.append(output_file)
  assert filecmp.cmp(*outputs, shallow=False)


def test_pre_commit_hook(tmp_path):
  import yaml

  plugin = str(tmp_path / "plugin")
  client = str(tmp_path / "client")
  os.mkdir(plugin)
  os.mkdir(client)
  root = os.path.dirname(os.path.dirname(__file__))
  for filename in (
    "pyproject.toml", "gas_arm_format.py", "README.md", "LICENSE", ".pre-commit-hooks.yaml", "MANIFEST.in",
  ):
    shutil.copyfile(f"{root}/{filename}", f"{plugin}/{filename}")
  shutil.copytree(f"{root}/tests", f"{plugin}/tests", ignore=shutil.ignore_patterns("__pycache__"))
  subprocess.run(["git", "init", "--quiet", plugin], check=True)
  subprocess.run(["git", "add", "."], cwd=plugin, check=True)
  subprocess.run([
    "git", "-c", "user.name=Formatter tests", "-c", "user.email=tests@example.invalid",
    "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "feat: add GNU ARM formatting hook",
  ], cwd=plugin, check=True)
  revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=plugin, text=True).strip()
  subprocess.run(["git", "init", "--quiet", client], check=True)
  for filename in ("one.s", "two.S"):
    with open(f"{client}/{filename}", "w", -1, "utf8", None, "\n") as writer:
      writer.write("mov r0,r1\n")
  subprocess.run(["git", "add", "."], cwd=client, check=True)
  config = f"{tmp_path}/config.yaml"
  with open(config, "w", -1, "utf8", None, "\n") as writer:
    yaml.safe_dump({"repos": [{"repo": plugin, "rev": revision, "hooks": [{"id": "gas-arm-format"}]}]}, writer)
  command = [sys.executable, "-m", "pre_commit", "run", "--config", config, "--files", "one.s", "two.S"]
  changed = subprocess.run(command, cwd=client, capture_output=True, text=True)
  assert changed.returncode == 1, changed.stdout + changed.stderr
  assert "files were modified by this hook" in changed.stdout
  for filename in ("one.s", "two.S"):
    with open(f"{client}/{filename}", "r", -1, "utf8") as reader:
      assert reader.read() == "  mov r0, r1\n"
  checked = subprocess.run(command, cwd=client, capture_output=True, text=True)
  assert checked.returncode == 0, checked.stdout + checked.stderr
