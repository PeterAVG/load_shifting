VENV_DIR = .venv

clean:
	rm -rf *.aux *.dvi *.log *.pdf *.synctex.gz $(VENV_DIR) poetry.lock venv_julia .tmp .mypy_cache .pytest_cache

dev-setup: $(VENV_DIR)/.made
	$(VENV_DIR)/bin/pre-commit install -ft pre-push
	$(VENV_DIR)/bin/pre-commit install -ft pre-commit

$(VENV_DIR)/.made:
	python3 -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install --upgrade pip
	poetry install
	touch $@
