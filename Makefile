.PHONY: install update sync clean help

help:
	@echo ""
	@echo "  hackbot — Autonomous Bug Bounty Pipeline"
	@echo ""
	@echo "  Targets:"
	@echo "    make install    Run interactive setup (./setup.sh)"
	@echo "    make update     Pull latest changes and re-install"
	@echo "    make sync       Sync live files back to repo (author only)"
	@echo "    make clean      Remove installed hackbot files"
	@echo ""

install:
	./setup.sh

update:
	./update.sh

sync:
	./scripts/sync-to-repo.sh

clean:
	rm -rf ~/.hackbot
	rm -rf ~/Projects/hackbot-misc
	@echo "Cleaned hackbot install directories"
