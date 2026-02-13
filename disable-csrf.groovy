import jenkins.model.Jenkins

def instance = Jenkins.getInstance()
instance.setCrumbIssuer(null)
instance.save()

println "CSRF protection disabled"
