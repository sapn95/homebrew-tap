# frozen_string_literal: true

# This is the formula; sapn95/homebrew-tap carries a copy of it so that
# `brew install sapn95/tap/tokendealer` works. The tap's hourly updater takes
# this file out of whichever release is newest, points its urls at that
# release and writes each sha256 from the archive it downloaded.
class Tokendealer < Formula
  desc "Knows what each coding-assistant subscription has left, keeps work and private apart"
  homepage "https://github.com/sapn95/tokendealer"
  version "0.1.1"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/sapn95/tokendealer/releases/download/v0.1.1/tokendealer-v0.1.1-aarch64-apple-darwin.tar.gz"
      sha256 "2046f7b1a9d2e874cb97abd564a288651a6bc1b8ef39b8cf7a44a10698c92349"
    end
    on_intel do
      url "https://github.com/sapn95/tokendealer/releases/download/v0.1.1/tokendealer-v0.1.1-x86_64-apple-darwin.tar.gz"
      sha256 "ae4149190fa2920e32a6e0a35bf98e9940f2b920900f874c55cde45178435feb"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/sapn95/tokendealer/releases/download/v0.1.1/tokendealer-v0.1.1-aarch64-unknown-linux-musl.tar.gz"
      sha256 "6bbcebc9fef668ae6e0140e783fc6ab590158e2ddb2a6a92c11e421a13194135"
    end
    on_intel do
      url "https://github.com/sapn95/tokendealer/releases/download/v0.1.1/tokendealer-v0.1.1-x86_64-unknown-linux-musl.tar.gz"
      sha256 "e3a9754efab5d1e24dd6fd7c07745215b561c556aa4a97ae1b219821a22e4aed"
    end
  end

  def install
    bin.install "tokendealer"
  end

  test do
    assert_match(/^tokendealer \d+\.\d+\.\d+$/, shell_output("#{bin}/tokendealer --version"))
  end
end
