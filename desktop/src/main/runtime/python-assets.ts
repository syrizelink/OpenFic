export interface PythonAsset {
  version: string;
  tag: string;
  target: string;
  urls: string[];
}

const PYTHON_VERSION = "3.13.14";
const RELEASE_TAG = "20260623";
const GITHUB_BASE_URL = `https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}`;
const MIRROR_PREFIX = "https://gh-proxy.com/";

function buildGithubUrl(target: string): string {
  const filename = `cpython-${PYTHON_VERSION}+${RELEASE_TAG}-${target}-install_only.tar.gz`;
  return `${GITHUB_BASE_URL}/${encodeURIComponent(filename).replace(/%2F/g, "/")}`;
}

function buildAsset(target: string): PythonAsset {
  const githubUrl = buildGithubUrl(target);
  return {
    version: PYTHON_VERSION,
    tag: RELEASE_TAG,
    target,
    urls: [githubUrl, `${MIRROR_PREFIX}${githubUrl}`],
  };
}

export function resolvePythonAsset(platform = process.platform, arch = process.arch): PythonAsset {
  if (platform === "win32" && arch === "x64") return buildAsset("x86_64-pc-windows-msvc");
  if (platform === "linux" && arch === "x64") return buildAsset("x86_64-unknown-linux-gnu");
  if (platform === "darwin" && arch === "arm64") return buildAsset("aarch64-apple-darwin");
  if (platform === "darwin" && arch === "x64") return buildAsset("x86_64-apple-darwin");
  throw new Error(`unsupported platform for portable Python: ${platform}/${arch}`);
}
