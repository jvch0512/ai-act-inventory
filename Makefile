.PHONY: build test sample

test:
	python3 -m unittest discover -s tests -v

sample:
	mkdir -p docs site
	bin/ai-act-inventory examples > docs/sample-output.txt; true
	bin/ai-act-inventory examples --tsv > docs/sample-output.tsv; true
	python3 scripts/site.py docs/sample-output.tsv site/index.html "ai-act-inventory" "Checks an inventory of AI systems against the EU AI Act: prohibited practices, high-risk misclassification, missing human oversight, logging, data governance and transparency notices. Python." "Synthetic data."
