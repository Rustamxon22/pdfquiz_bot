def parse_quiz(text):
    blocks = text.split("++++")
    questions = []

    for block in blocks:
        parts = block.strip().split("====")
        if len(parts) < 4:
            continue

        question = parts[0].strip()

        options = []
        correct = ""

        for p in parts[1:]:
            p = p.strip()
            if p.startswith("#"):
                correct = p[1:]
                options.append(p[1:])
            else:
                options.append(p)

        questions.append({
            "question": question,
            "options": options,
            "correct": correct
        })

    return questions