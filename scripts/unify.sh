#!/usr/bin/env bash
# Script para unificar varios archivos de una extension en otros para así poder correr moss de forma simple
# forma de ejecucion: 
# ./unify <PATH> <EXTENSION>
# Ejemplo: 
# ./unify ../../entregas/parcialitos/2021_1/parcialito1 c

ACTUAL=`pwd`
cd $1
for dir in ./*/
do
	dir=${dir%*/} 
	# En caso de ya existir o necesitar hacer una segunda pasada
	rm -f $dir/PARCIALITO1_AUTOGEN.$2
	for file in $dir/*.$2
	do
		cat "${file}" >> $dir/PARCIALITO1_AUTOGEN.$2
	done
done
cd $ACTUAL