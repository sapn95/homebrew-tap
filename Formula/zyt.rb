# frozen_string_literal: true

# This is the formula; sapn95/homebrew-tap carries a copy of it so that
# `brew install sapn95/tap/zyt` works beside the other tools. The body has to
# be copied there by hand once, which is the price of the shorter install
# line. After that the tap's hourly updater takes this file out of whichever
# release is newest and keeps its own copy current.
#
# The two lines below are allowed to fall behind that newest release, and they
# will: a checksum cannot be written before the tag it belongs to exists, so
# the copy of this file inside any release's tarball names the release before
# it. Nobody installs from here, and the tap rewrites both lines from the
# tarball it actually downloaded.
class Zyt < Formula
  desc "Work or private: a Hammerspoon time tracker that knows the difference"
  homepage "https://github.com/sapn95/zyt"
  url "https://github.com/sapn95/zyt/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "88aeb5d9da56e1fcc9552f815fd857afb5c436c0f0f9d3732ebcf52af0d4a66e"
  license "MIT"
  head "https://github.com/sapn95/zyt.git", branch: "main"

  depends_on :macos

  def install
    # The Spoon cannot be linked into ~/.hammerspoon from here: a formula must
    # not write to a home directory. `zyt link` is the step that does.
    libexec.install "Zyt.spoon"
    bin.install "scripts/zyt"
  end

  def caveats
    <<~CAVEATS
      Link the Spoon into Hammerspoon and add the line it prints to
      ~/.hammerspoon/init.lua:

        zyt link

      Then write ~/.config/zyt/rules.json (examples/rules.json in the
      repository is a start), reload Hammerspoon, and check the result:

        zyt doctor
    CAVEATS
  end

  test do
    assert_predicate libexec/"Zyt.spoon/init.lua", :exist?
    # Not the formula's own version: a --HEAD build calls itself HEAD-<sha>,
    # and the command would then fail a test for saying what it really is.
    assert_match(/^zyt \d+\.\d+\.\d+$/, shell_output("#{bin}/zyt --version"))
    assert_match "usage:", shell_output("#{bin}/zyt 2>&1", 2)
  end
end
