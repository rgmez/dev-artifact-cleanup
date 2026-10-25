#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"

FIXTURES = Dir[File.join(__dir__, "fixtures", "*.json")].sort.freeze
REQUIRED_CANDIDATE_FIELDS = %w[
  id path resolvedPath approvedRoot class sizeBytes evidence risk auditRecommendation snapshot
].freeze

def contained_by_root?(path, root)
  path == root || path.start_with?("#{root}/")
end

def validate_candidate(candidate, ids)
  missing = REQUIRED_CANDIDATE_FIELDS.reject { |field| candidate.key?(field) }
  abort("#{candidate["id"] || "unknown"}: missing #{missing.join(", ")}") unless missing.empty?
  abort("candidate id is duplicated: #{candidate["id"]}") if ids.include?(candidate["id"])
  ids << candidate["id"]

  %w[path resolvedPath approvedRoot].each do |field|
    abort("#{candidate["id"]}: #{field} must be absolute") unless candidate[field].start_with?("/")
  end
  abort("#{candidate["id"]}: resolved path outside root") unless contained_by_root?(candidate["resolvedPath"], candidate["approvedRoot"])
  abort("#{candidate["id"]}: symlink candidates are invalid") unless candidate.fetch("snapshot").fetch("isSymbolicLink") == false
end

abort("no fixtures found") if FIXTURES.empty?

FIXTURES.each do |fixture|
  manifest = JSON.parse(File.read(fixture))
  %w[schemaVersion auditId createdAt mode approvedRoots approvedCandidateIds candidates].each do |field|
    abort("#{fixture}: missing #{field}") unless manifest.key?(field)
  end
  abort("#{fixture}: wrong schema version") unless manifest["schemaVersion"] == 1
  abort("#{fixture}: invalid mode") unless %w[audit execute].include?(manifest["mode"])
  abort("#{fixture}: duplicate approved ids") unless manifest["approvedCandidateIds"].uniq == manifest["approvedCandidateIds"]

  ids = []
  manifest.fetch("candidates").each { |candidate| validate_candidate(candidate, ids) }

  if manifest["mode"] == "audit"
    abort("#{fixture}: audit cannot approve candidates") unless manifest["approvedCandidateIds"].empty?
    abort("#{fixture}: audit cannot include execution") if manifest.key?("execution")
  else
    execution = manifest.fetch("execution")
    approved = manifest.fetch("approvedCandidateIds")
    abort("#{fixture}: execute requires approved ids") if approved.empty?
    abort("#{fixture}: authorization differs from approved ids") unless execution.fetch("authorizedCandidateIds").sort == approved.sort
    approved.each do |id|
      candidate = manifest.fetch("candidates").find { |entry| entry["id"] == id }
      abort("#{fixture}: approved candidate missing") unless candidate
      abort("#{fixture}: only worktrees use execute-mode fixtures; cache approval is separate") unless candidate["class"] == "worktree"
      abort("#{fixture}: only secondary worktrees execute") unless candidate.fetch("snapshot")["worktreeRole"] == "secondary"
      abort("#{fixture}: candidate not eligible") unless candidate["risk"] == "safe-candidate" && candidate["auditRecommendation"] == "eligible-for-execution"
    end
  end
end

puts "fixture contracts valid: #{FIXTURES.length}"
