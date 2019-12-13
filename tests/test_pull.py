import subprocess


def test_pull(tmp_path):
    result = subprocess.run(
        ["./enki", "pull", "library/ubuntu"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True
    )
    image_id = result.stdout.decode("utf-8").strip()

    result = subprocess.run(
        ["./enki", "run", image_id, "--", "/bin/bash", "-c", "echo test"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True
    )
    assert result.stdout == b"test\n"
