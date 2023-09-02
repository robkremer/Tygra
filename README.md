# tygra
## A model/view typed graph editor 
## Rob Kremer, @robkremer

This is a visual graph editor ("graph" as in nodes and edges), where a node is called
a *node* and an edge is called a *relation*.  Nodes and relations are typed in that
there types dictate thier *attributes* such as fill colour, border colour, text colour,
shape, aspect ratio, and minimum size as well as thier properties such the tranitive,
symetric, and reflexive properties or relations. 

![Screenshot of a tygra file window (displaying some info about tygra iteself)]
(images/sampleModel.png)

![Screenshot of a tygra view window (displaying a view of the above model))

The type of a node or relation is
specified by drawing an *ISA* relation from the subsumed node or relation to the
subsuming node or relation (where the subsumming node or relation must have the
*type* property).

Because graphs can become large and complicated quickly, *tygra* follows the 
model/view pattern.  A model is a semantic description of a graph, containing all
the nodes (and thier attributes such as label, various colours, shape) and
relations between the nodes (and the relations themselves).  For each model
there is one or more views which reference the single model, and may contain
all, or just some of, the model's nodes and relations. Views contain only 
syntactic information such as which nodes and relations are displayed and
thier locations on the view canvas.  

A file may contain several models, as well as several views, each referencing
a single model within the file. This restriction will eventually be lifted as
I am planning to all views to reference mulitple models.  In addition, eventually
models will be able to reference other models. Both models and views will
eventually be able to reference other models and views in remote web URIs as well.
as 
