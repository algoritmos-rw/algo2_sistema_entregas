import os, sys, shutil, glob, re, subprocess, threading

MERGED_FILE = "merged.out"
GS_CMD = "gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite".split(" ")


def generate(directory, pdf_directory, lang):
	os.chdir(directory)
	generate_merged_files()
	os.mkdir(pdf_directory)
	# TODO: Habria que pasar esto a subprocess.call pero con el piping que tiene creo que perderia un tanto de tiempo haciendolo
	os.popen("""find * -iname """ + MERGED_FILE + """ -exec bash -c 'enscript -b "$(dirname "{}")||$%/$=" -E""" + lang + """ --color=1 -fCourier8 -X 88591 -o - "{}" | ps2pdf - """ + pdf_directory + """/$(dirname "{}").pdf' \;""")


def generate_merged_files(directory = '.'):
	for dirpath, dirnames, filenames in os.walk(directory, 1):
		outfilename = f"{dirpath}/" + MERGED_FILE
		with open(f"{outfilename}", 'wb') as outfile:
			matches = 0
			for filename in glob.glob(f"{dirpath}/**", recursive=True):
				# Only get files .py or .c or .txt that are not named _mensaje.txt
				if re.match('^(?:(?!(?:.*\/)?_mensaje\.txt).*\.txt)|(?:.*\.py$)|(?:.*\.c$)', filename):
					with open(filename, 'rb') as readfile:
						shutil.copyfileobj(readfile, outfile)
					matches += 1
		if matches == 0:
			print("Revisar " + dirpath + " (potencialmente envio pdfs o con subdirectorios)")


def add_images_to_exam(pdf_directory, dirpath):
	images = []
	for filename in glob.glob(f"{dirpath}/**", recursive=True):
		# Only get image files .jpg, .png, .jpeg, .gif
		if re.match('^(?:.*\.png$)|(?:.*\.jpg$)|(?:.*\.jpeg$)|(?:.*\.gif$)|(?:.*\.pdf$)', filename):
			name_in_pdf = ".".join(filename.split(".")[:-1]) + ".pdf"
			if filename != name_in_pdf:
				# Need to ensure that the file will exist before performing the join with gs
				subprocess.call(["convert", filename, name_in_pdf])
			images.append(name_in_pdf)
	if len(images) > 0 :
		pdf_path = f"{pdf_directory}/{dirpath[2:]}.pdf"
		pdf_copy = f"{pdf_directory}/{dirpath[2:]}_copy.pdf"
		subprocess.call(["cp", pdf_path, pdf_copy])
		subprocess.call(GS_CMD + ["-sOutputFile=" + pdf_path] + [pdf_copy] + images)
		subprocess.Popen(["rm", pdf_copy])


def add_images(directory, pdf_directory):
	os.chdir(directory)
	threads = []
	for dirpath, dirnames, filenames in os.walk('.', 1):
		if dirpath == '.':
			continue
		t = threading.Thread(target=add_images_to_exam, args=(pdf_directory, dirpath))
		t.start()
		threads.append(t)
	for t in threads:
		t.join()


if __name__ == "__main__":
	if len(sys.argv) < 4:
		print("""
Uso:
	1. path a la carpeta con parciales
	2. nombre de carpeta donde poner los pdfs
	3. comando a ejecutar:
		- generate_pdfs
		- attach_images
			""")
	if sys.argv[3] == "generate":
		generate(sys.argv[1], sys.argv[2], sys.argv[4])
	else:
		add_images(sys.argv[1], sys.argv[2])
