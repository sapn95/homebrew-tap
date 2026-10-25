# frozen_string_literal: true

# A copy of sapn95/zyt's own Formula/zyt.rb, so that the install line is
# `brew install --HEAD sapn95/tap/zyt` like the other tools here. The project
# is the place to change it; this file is copied by hand.
#
# Head-only on purpose: zyt has no tagged release, and a formula with no tag in
# its urls is one `scripts/update_formulae.py` skips rather than rewrites, so
# nothing here will quietly strip the install block. When zyt tags a release,
# this file gets a url and a sha256 and the updater takes it from there.
class Zyt < Formula
  desc "Work or private: a Hammerspoon time tracker that knows the difference"
  homepage "https://github.com/sapn95/zyt"
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
    assert_match "usage:", shell_output("#{bin}/zyt 2>&1", 2)
  end
end
